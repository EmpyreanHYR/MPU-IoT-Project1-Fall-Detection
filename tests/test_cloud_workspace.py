"""Cloud archive and offline behavior using synthetic records and a private fixture."""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workspace',ROOT/'webui/cloud_workspace.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class CloudWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.db=self.path/'events.sqlite3'
        with closing(sqlite3.connect(self.db)) as db,db:
            db.execute('CREATE TABLE edge_records(record_id TEXT PRIMARY KEY,device_id TEXT,captured_at TEXT,received_at TEXT,payload TEXT)')
            for i,state in enumerate(['normal','suspected','confirmed']):
                stamp=f'2026-10-06T16:0{i}:00Z';payload=dict(timestamp=stamp,device_id='fixture',alert_state=state,fall_probability=i/3,record_id=str(i))
                db.execute('INSERT INTO edge_records VALUES(?,?,?,?,?)',(str(i),'fixture',stamp,stamp,json.dumps(payload)))
        self.workspace=module.Workspace(self.db,ROOT/'webui/index.html',lambda action,client:(200,{'running':action=='start'}))
    def tearDown(self):self.tmp.cleanup()
    def test_archive_filter_pagination_and_capture_time(self):
        data=self.workspace.records({'state':['confirmed'],'from':['2026-10-07T00:01:00+08:00']})
        self.assertEqual(data['total'],1);self.assertEqual(data['records'][0]['timestamp'],'2026-10-06T16:02:00Z')
        self.assertTrue(data['records'][0]['delivered'])
        self.assertEqual(self.workspace.records({'limit':['1'],'offset':['1']})['records'][0]['alert_state'],'suspected')
        with self.assertRaises(ValueError):self.workspace.records({'delivery':['pending']})
    def test_edge_loss_preserves_cloud_archive_without_fake_current_score(self):
        data=self.workspace.status()
        self.assertEqual(data['total_records'],3);self.assertTrue(data['storage_available'])
        self.assertFalse(data['edge_connected']);self.assertIsNone(data['pending_records'])
        self.assertEqual(data['runtime'],{});self.assertIsNone(data['runtime_age_s'])
        self.assertEqual(len(data['trend']),3)
    def test_private_status_uses_device_token(self):
        requests=[]
        class Private(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                requests.append((self.path,self.headers.get('X-Device-Token')))
                payload={'runtime':{'valid_pose':False,'last_prediction':.95},'runtime_age_s':.1,'pending_records':4,'telemetry':{'cpu_temperature_c':42}}
                data=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        private=ThreadingHTTPServer(('127.0.0.1',0),Private);thread=threading.Thread(target=private.serve_forever,daemon=True);thread.start()
        self.workspace.edge_url=f'http://127.0.0.1:{private.server_port}';self.workspace.edge_token='synthetic-token'
        try:
            data=self.workspace.status();self.assertTrue(data['edge_connected']);self.assertEqual(data['pending_records'],4)
            self.assertFalse(data['runtime']['valid_pose']);self.assertEqual(requests,[('/dashboard/status','synthetic-token')])
            self.workspace.status();self.assertEqual(len(requests),1)
        finally:private.shutdown();private.server_close();thread.join()
    def test_control_requires_origin_and_token(self):
        self.workspace.public_origin='https://example.test:2622';self.workspace.camera_enabled=True
        responses=[]
        class Handler:
            path='/api/workspace/camera';headers={'Origin':'https://evil.test','Content-Type':'application/json','X-Control-Token':'bad'}
            def read_json(self,*_):return {'action':'start'}
        with patch.object(self.workspace,'send',side_effect=lambda h,c,p,*args:responses.append((c,p))):
            self.workspace.post(Handler());self.assertEqual(responses[-1][0],403)
            Handler.headers={'Origin':self.workspace.public_origin,'Content-Type':'application/json','X-Control-Token':self.workspace.token}
            self.workspace.post(Handler());self.assertEqual(responses[-1],(200,{'state':'active','error':None}))
            Handler.read_json=lambda *_:{'action':'restart'}
            self.workspace.post(Handler());self.assertEqual(responses[-1][0],400)
    def test_restarts_do_not_change_history(self):
        second=module.Workspace(self.db,ROOT/'webui/index.html',lambda *_:None)
        self.assertEqual(second.records({})['total'],3)
        self.assertEqual(second.status()['state_counts']['confirmed'],1)

if __name__=='__main__':unittest.main()
