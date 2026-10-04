"""Durability, retry idempotency, transactional rollback and input-window tests."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime,timezone,timedelta
from contextlib import closing
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deployment/edge'))
from edge_runtime import Store,Classifier,utc,start_api

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'webui'))
sys.path.insert(0,str(ROOT/'deployment/cloud'))
TEMP=tempfile.TemporaryDirectory()
os.environ['FALLGUARD_DATA_DIR']=TEMP.name
os.environ['FALLGUARD_INGEST_TOKEN']='local-test-token'
import server
from edge_ingest import import_records
from pull_edge_records import sync_once,request

class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'edge.db')
        self.db=Path(self.tmp.name)/'cloud.db';server.DB_PATH=self.db;self.state=server.State()
    def tearDown(self):self.tmp.cleanup()
    def record(self,p=.9):
        return self.store.add({'device_id':'test-pi','timestamp':utc(),'frame_seq':1,
            'fall_probability':p,'pose_quality':.8,'model':'test-local'})
    def ingest(self,records):
        return import_records(self.state,self.db,{'records':records},server.validate_reading,utc)
    def test_restart_and_state_durability(self):
        a=self.record();self.store=Store(self.store.path);b=self.record()
        self.assertEqual([a['transition'],b['transition']],['suspected','confirmed'])
        self.assertEqual(self.store.pending(),[a,b]);self.store.acknowledge([a['record_id']])
        self.assertEqual(Store(self.store.path).pending(),[b])
    def test_lost_ack_cloud_restart_and_duplicate(self):
        records=[self.record(),self.record(),self.record(.1),self.record(.1)]
        self.assertEqual(self.ingest(records)['events_created'],3)
        self.state=server.State();self.assertEqual(self.ingest(records)['inserted'],0)
        self.assertEqual(len(self.state.events()),3)
        self.store.acknowledge([x['record_id'] for x in records]);self.assertEqual(self.store.pending(),[])
    def test_batch_collision_rolls_back(self):
        first=self.record();self.ingest([first]);new=self.record();bad=dict(first,fall_probability=.1)
        with self.assertRaises(ValueError):self.ingest([new,bad])
        with closing(sqlite3.connect(self.db)) as db:self.assertEqual(db.execute('select count(*) from edge_records').fetchone()[0],1)
    def test_preserve_offline_time(self):
        record=self.record();record['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.ingest([record]);self.assertEqual(self.state.events()[0]['timestamp'],record['timestamp'])
        self.assertFalse(self.state.snapshot()['devices'][0]['online'])
        self.state=server.State()
        device=self.state.snapshot()['devices'][0]
        self.assertEqual(device['timestamp'],record['timestamp'])
        self.assertFalse(device['online'])
    def test_http_sync_and_authentication(self):
        from http.server import ThreadingHTTPServer
        from urllib.error import HTTPError
        server.STATE=self.state;edge=start_api(self.store,'127.0.0.1',0,'edge-test',{})
        cloud=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=cloud.serve_forever,daemon=True).start()
        e=f'http://127.0.0.1:{edge.server_port}';c=f'http://127.0.0.1:{cloud.server_port}'
        try:
            records=[self.record() for _ in range(205)]
            with self.assertRaises(HTTPError):sync_once(e,'edge-test',c,'wrong-token')
            self.assertEqual(self.store.stats()['pending_records'],205)
            result=sync_once(e,'edge-test',c,'local-test-token')
            self.assertEqual(result['inserted'],100)
            self.assertEqual(sync_once(e,'edge-test',c,'local-test-token')['inserted'],100)
            self.assertEqual(sync_once(e,'edge-test',c,'local-test-token')['inserted'],5)
            self.assertEqual(self.store.pending(),[])
            self.assertEqual(sync_once(e,'edge-test',c,'local-test-token')['inserted'],0)
        finally:edge.shutdown();cloud.shutdown();edge.server_close();cloud.server_close()
    def test_window_matches_training_and_resets_gap(self):
        clf=Classifier.__new__(Classifier);from collections import deque
        clf.frames=deque();clf.last_prediction=-1e10;clf.names={'pose','quality'}
        class Session:
            def run(self,_,inputs):self.inputs=inputs;return [np.array([[0.,1.]])]
        clf.session=Session();points=np.zeros((17,3),np.float32)
        points[:,0]=np.arange(17)/17;points[:,1]=np.arange(17)/34;points[:,2]=.9
        for i in range(31):result=clf.add(i/30,points,.4+i/100)
        self.assertIsNotNone(result)
        self.assertEqual(clf.session.inputs['pose'].shape,(1,30,36))
        np.testing.assert_allclose(clf.session.inputs['quality'][0,:,2],.4+np.arange(30)/100,atol=1e-6)
        self.assertIsNone(clf.add(2.,points,.9));self.assertEqual(len(clf.frames),1)

if __name__=='__main__':unittest.main(verbosity=2)
