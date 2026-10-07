"""Verify dashboard archive queries and the local control boundary on synthetic data."""
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import gzip
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard', ROOT/'deployment/edge/local_dashboard.py')
dash = importlib.util.module_from_spec(spec); spec.loader.exec_module(dash)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.db = self.root/'edge.sqlite3'; self.status = self.root/'status.json'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE outbox(seq INTEGER PRIMARY KEY,record_id TEXT,payload TEXT,acknowledged REAL)')
            for i, state in enumerate(['normal','suspected','confirmed','cleared']):
                payload = dict(timestamp=f'2026-10-06T16:0{i}:00+00:00', device_id='=test-fixture',
                               fall_probability=i/4, alert_state=state, record_id=str(i))
                db.execute('INSERT INTO outbox VALUES(?,?,?,?)', (i,str(i),json.dumps(payload),time.time() if i%2==0 else None))
        self.status.write_text(json.dumps(dict(backend='hailo',valid_pose=False,last_prediction=.9,
                                  last_prediction_at='2026-01-01T00:00:00Z')))
        args = SimpleNamespace(port=0,status=self.status,database=self.db,preview=self.root/'preview.jpg',camera_service=None)
        db.close()
        self.server = dash.make_server(args); self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base=f'http://127.0.0.1:{self.port}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def get(self,path):
        with urlopen(self.base+path,timeout=3) as response: return response.read()
    def test_archive_filters_and_pagination(self):
        data=json.loads(self.get('/api/records?delivery=pending&limit=1'))
        self.assertEqual(data['total'],2); self.assertEqual(data['records'][0]['alert_state'],'cleared')
        data=json.loads(self.get('/api/records?delivery=pending&limit=1&offset=1'))
        self.assertEqual(data['records'][0]['alert_state'],'suspected')
        data=json.loads(self.get('/api/records?state=confirmed&from=2026-10-07T00:01:00%2B08:00&to=2026-10-07T00:02:30%2B08:00'))
        self.assertEqual(data['total'],1)
        self.assertEqual(json.loads(self.get('/api/records?state=normal&delivery=pending'))['total'],0)
    def test_bad_query_is_rejected(self):
        for query in ['state=invalid', 'delivery=invalid','limit=bad','from=bad']:
            with self.assertRaises(HTTPError) as error:self.get('/api/records?'+query)
            self.assertEqual(error.exception.code,400); error.exception.close()
    def test_export_is_filtered_and_formula_safe(self):
        export=self.get('/api/export.csv?state=normal').decode('utf-8-sig')
        self.assertEqual(len(export.splitlines()),2)
        self.assertIn("'=test-fixture", export); self.assertIn(',0.0,normal,',export)
    def test_snapshot_preserves_queues_and_historical_times(self):
        data=json.loads(self.get('/api/status'))
        self.assertEqual(data['total_records'],4); self.assertEqual(data['pending_records'],2)
        self.assertFalse(data['runtime']['valid_pose']); self.assertEqual(data['runtime']['last_prediction_at'],'2026-01-01T00:00:00Z')
        self.assertEqual(data['state_counts']['confirmed'],1); self.assertFalse(data['camera_control']['enabled'])
        self.assertEqual(data['trend'][0]['alert_state'],'normal')
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM outbox').fetchone()[0],4)
        db.close()
    def test_foreign_host_is_rejected(self):
        for host in ['evil.example',f'localhost:{self.port+1}']:
            with self.assertRaises(HTTPError) as error:urlopen(Request(self.base+'/api/status',headers={'Host':host}),timeout=3)
            self.assertEqual(error.exception.code,403); error.exception.close()
    def test_camera_control_requires_origin_token_and_json(self):
        html=self.get('/').decode();token=re.search(r'name="control-token" content="([^"]+)"',html).group(1)
        headers={'Origin':self.base,'Content-Type':'application/json','X-Control-Token':token}
        for changed in [{'Origin':'https://evil.example'},{'X-Control-Token':'wrong'},{'Content-Type':'text/plain'}]:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+'/api/camera',data=b'{"action":"stop"}',headers={**headers,**changed}),timeout=3)
            self.assertEqual(error.exception.code,403); error.exception.close()
        # Optional control is disabled unless explicitly configured.
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/camera',data=b'{"action":"start"}',headers=headers),timeout=3)
        self.assertEqual(error.exception.code,400); error.exception.close()
    def test_compressed_responses(self):
        req=Request(self.base+'/api/status',headers={'Accept-Encoding':'gzip'})
        with urlopen(req,timeout=3) as response:
            self.assertEqual(response.headers['Content-Encoding'],'gzip')
            data=json.loads(gzip.decompress(response.read()))
        self.assertEqual(data['total_records'],4)
    def test_service_control_only_runs_fixed_argv(self):
        control=dash.CameraControl('fallguard-camera.service')
        with patch.object(dash.subprocess,'run') as run:
            run.return_value=SimpleNamespace(stdout='active\n')
            self.assertEqual(control.action('start')['state'],'active')
            self.assertEqual(run.call_args_list[0].args[0],['/usr/bin/systemctl','--user','start','fallguard-camera.service'])
            with self.assertRaises(ValueError):control.action('restart; rm -rf /')
        with patch.object(dash.subprocess,'run') as run:
            run.return_value=SimpleNamespace(stdout='inactive\n')
            self.assertEqual(control.action('stop')['state'],'inactive')
    def test_missing_database_and_stale_preview_are_unavailable(self):
        preview=self.root/'preview.jpg';preview.write_bytes(b'not-a-real-image')
        import os
        os.utime(preview,(time.time()-10,time.time()-10))
        with self.assertRaises(HTTPError) as error:self.get('/preview.jpg')
        self.assertEqual(error.exception.code,503); error.exception.close()
        self.db.unlink()
        self.assertFalse(json.loads(self.get('/api/status'))['storage_available'])
        with self.assertRaises(HTTPError) as error:self.get('/api/records')
        self.assertEqual(error.exception.code,503); error.exception.close()

if __name__=='__main__':unittest.main()
