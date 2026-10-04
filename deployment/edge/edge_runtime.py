"""Offline pose -> 1-second window -> fall classification with durable outbox.

Inference has no network dependency. The cloud pulls records from the authenticated
outbox and acknowledges UUIDs only after its own database transaction commits.
"""
from __future__ import annotations
import argparse
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
import uuid
import cv2
import numpy as np
import onnxruntime as ort
from pose_backend import HailoPose, CpuPose, annotate
from video_input import VideoInput,CameraInput


def utc(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat(timespec='milliseconds')


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS outbox (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, created REAL NOT NULL, acknowledged REAL);
                CREATE TABLE IF NOT EXISTS alert_state (
                    device TEXT PRIMARY KEY, state TEXT, high INTEGER, low INTEGER, last_epoch REAL);
                CREATE INDEX IF NOT EXISTS pending ON outbox(acknowledged,seq);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:yield db
        finally:db.close()

    def add(self, record):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT state,high,low,last_epoch FROM alert_state WHERE device=?',
                                  (record['device_id'],)).fetchone()
            state, high, low, last = previous or ('normal', 0, 0, 0.)
            now = time.time()
            if now-last > 2: high = low = 0
            probability = record['fall_probability']
            transition = None
            if probability >= .65:
                high, low = high+1, 0
                if state in ('normal', 'cleared'): state = transition = 'suspected'
                if high >= 2 and probability >= .82 and state == 'suspected':
                    state = transition = 'confirmed'
            elif probability <= .35:
                high, low = 0, low+1
                if state in ('suspected', 'confirmed') and low >= 2: state = transition = 'cleared'
                elif state == 'cleared': state = 'normal'
            else: high = low = 0
            record = dict(record, record_id=str(uuid.uuid4()), alert_state=state, transition=transition)
            db.execute('INSERT INTO outbox(record_id,payload,created) VALUES(?,?,?)',
                       (record['record_id'], json.dumps(record, separators=(',',':')), now))
            db.execute('INSERT OR REPLACE INTO alert_state VALUES(?,?,?,?,?)',
                       (record['device_id'],state,high,low,now))
        return record

    def pending(self, limit=100):
        with self.connect() as db:
            return [json.loads(x[0]) for x in db.execute(
                'SELECT payload FROM outbox WHERE acknowledged IS NULL ORDER BY seq LIMIT ?', (limit,))]

    def acknowledge(self, ids):
        if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(x,str) or len(x)!=36 for x in ids):
            raise ValueError('at most 100 record UUIDs required')
        with self.connect() as db:
            db.executemany('UPDATE outbox SET acknowledged=? WHERE record_id=? AND acknowledged IS NULL',
                           [(time.time(),x) for x in ids])
        return len(ids)

    def stats(self):
        with self.connect() as db:
            total, pending = db.execute('SELECT count(*),sum(acknowledged IS NULL) FROM outbox').fetchone()
        return {'total_records':total,'pending_records':pending or 0}


class Classifier:
    def __init__(self, model):
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
        self.names={i.name for i in self.session.get_inputs()}
        self.frames=deque();self.last_prediction=-1e10

    def reset(self):
        self.frames.clear();self.last_prediction=-1e10

    def add(self, stamp, points, box_confidence):
        if self.frames and (stamp<=self.frames[-1][0] or stamp-self.frames[-1][0]>.5):
            self.reset()
        self.frames.append((stamp,points.copy(),box_confidence))
        # Preserve one sample preceding the left interpolation boundary.
        while len(self.frames)>2 and self.frames[1][0]<stamp-1.:self.frames.popleft()
        if stamp-self.last_prediction < .2-1e-6 or stamp-self.frames[0][0]<1.-1e-6:return None
        self.last_prediction=stamp
        times=np.asarray([x[0] for x in self.frames])
        raw=np.stack([x[1][5:17] for x in self.frames])
        valid=np.sum(raw[:,:,2]>.2,axis=1)>=6
        if valid.mean()<.5:return None
        target=np.linspace(stamp-1.,stamp,30,endpoint=False)
        flat=raw.reshape(len(raw),36)
        sampled=np.stack([np.interp(target,times,flat[:,i]) for i in range(36)],axis=1).reshape(30,12,3)
        box=np.interp(target,times,[x[2] for x in self.frames])
        quality=np.stack([sampled[:,:,2].mean(1),(sampled[:,:,2]>=.2).mean(1),box],axis=1).astype(np.float32)
        for axis in (0,1):
            values=sampled[:,:,axis];lo=values.min(1,keepdims=True)
            sampled[:,:,axis]=(values-lo)/np.maximum(values.max(1,keepdims=True)-lo,1e-4)
        inputs={'pose':sampled.reshape(1,30,36).astype(np.float32)}
        if 'quality' in self.names:inputs['quality']=quality[None]
        start=time.perf_counter();logits=self.session.run(None,inputs)[0][0]
        elapsed=(time.perf_counter()-start)*1000
        exponents=np.exp(logits-logits.max());probability=float(exponents[1]/exponents.sum())
        return {'fall_probability':probability,'inference_ms':elapsed,
                'window_start':stamp-1.,'window_end':stamp,'window_observations':len(times),
                'pose_quality':float(quality[:,0].mean()),'valid_pose_fraction':float(valid.mean())}


def start_api(store, host, port, token, health):
    if not token:raise ValueError('FALLGUARD_INGEST_TOKEN required for outbox API')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,code,value):
            data=json.dumps(value).encode();self.send_response(code)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def authorized(self):
            if not hmac.compare_digest(self.headers.get('X-Device-Token',''),token):
                self.reply(401,{'error':'invalid device token'});return False
            return True
        def do_GET(self):
            if not self.authorized():return
            if self.path=='/records':self.reply(200,{'records':store.pending(),**store.stats()})
            elif self.path=='/health':self.reply(200,{**health,**store.stats()})
            else:self.reply(404,{'error':'not found'})
        def do_POST(self):
            if not self.authorized():return
            if self.path!='/ack':self.reply(404,{'error':'not found'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<5000:raise ValueError('invalid length')
                count=store.acknowledge(json.loads(self.rfile.read(length)).get('record_ids'))
                self.reply(200,{'acknowledged':count})
            except (ValueError,AttributeError):self.reply(400,{'error':'invalid acknowledgement'})
    server=ThreadingHTTPServer((host,port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='0',help='camera number or local video path')
    parser.add_argument('--backend',choices=['hailo','cpu','auto'],default='auto')
    parser.add_argument('--hef',default='/usr/share/hailo-models/yolov8s_pose_h10.hef')
    parser.add_argument('--cpu-model',default='yolov8n-pose.onnx')
    parser.add_argument('--classifier',default='masked_bimamba_quality.onnx')
    parser.add_argument('--database',default='data/edge.sqlite3')
    parser.add_argument('--device-id',default='pi5-offline')
    parser.add_argument('--duration',type=float,default=0.)
    parser.add_argument('--realtime',action='store_true',help='pace prerecorded video at original speed')
    parser.add_argument('--no-api',action='store_true')
    parser.add_argument('--bind',default=os.environ.get('FALLGUARD_RELAY_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=18082)
    parser.add_argument('--log',default='data/runtime.jsonl')
    parser.add_argument('--snapshot',default='',help='save one annotated input frame, for public test videos')
    parser.add_argument('--preview-file',default='',help='optional volatile local JPEG for authenticated dashboard preview')
    parser.add_argument('--status-file',default='')
    args=parser.parse_args()
    store=Store(args.database);classifier=Classifier(args.classifier)
    try:
        if args.backend=='cpu':raise ImportError('CPU selected')
        pose=HailoPose(args.hef);backend='hailo'
    except Exception:
        if args.backend=='hailo':raise
        if not Path(args.cpu_model).is_file():raise RuntimeError('Local CPU fallback weights are missing')
        pose=CpuPose(args.cpu_model);backend='cpu'
    health={'backend':backend,'classifier':str(args.classifier),'started_at':utc(),'ready':False}
    server=None if args.no_api else start_api(store,args.bind,args.port,os.environ.get('FALLGUARD_INGEST_TOKEN',''),health)
    live=args.source.isdecimal();cap=CameraInput(int(args.source)) if live else VideoInput(args.source)
    stopped=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.set())
    began=time.perf_counter();frames=0;predictions=0;saved=False;last_preview=0.;last_status=0.
    Path(args.log).parent.mkdir(parents=True,exist_ok=True)
    print(json.dumps({'started':health,'source':args.source,'network_required':False}),flush=True)
    try:
        with open(args.log,'a',buffering=1) as log:
            while not stopped.is_set() and (not args.duration or time.perf_counter()-began<args.duration):
                read_start=time.perf_counter();ok,frame=cap.read();capture_epoch=time.time()
                if not ok:break
                stamp=cap.stamp-began if live else cap.stamp
                if live:capture_epoch=cap.epoch
                if not live and args.realtime:
                    stopped.wait(max(0,stamp-(time.perf_counter()-began)))
                    capture_epoch=time.time()
                try:
                    points,box,timing=pose(frame)
                except Exception as exc:
                    if args.backend!='auto' or backend!='hailo':raise
                    print(json.dumps({'backend_failover':'cpu','reason':str(exc)}),flush=True)
                    pose.close();pose=CpuPose(args.cpu_model);backend='cpu';classifier.reset()
                    health['backend']=backend
                    points,box,timing=pose(frame)
                prediction=classifier.add(stamp,points,box)
                frames+=1
                entry={'frame':frames,'source_time':stamp,'capture_epoch':capture_epoch,
                       'valid_pose':bool((points[5:17,2]>.2).sum()>=6),**timing}
                if prediction:
                    predictions+=1
                    record=store.add(dict(prediction,device_id=args.device_id,timestamp=utc(capture_epoch),
                        frame_seq=frames,keypoints=points.tolist(),model='MaskedBiMamba local',
                        pose_backend=backend,source='edge_offline',
                        edge_fps=frames/max(time.perf_counter()-began,.001),**timing))
                    entry.update(record)
                    health.update(ready=True,last_prediction=record['fall_probability'],last_state=record['alert_state'],last_prediction_at=utc(capture_epoch))
                    if record['transition']:print(json.dumps(record),flush=True)
                health.update(last_frame=frames,last_capture_at=utc(capture_epoch),frames=frames,predictions=predictions,valid_pose=entry['valid_pose'])
                health['edge_fps']=frames/max(time.perf_counter()-began,.001)
                now=time.perf_counter()
                if args.status_file and now-last_status>=1:
                    status_path=Path(args.status_file);temporary=status_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps({**health,**store.stats()}));os.replace(temporary,status_path)
                    last_status=now
                if args.preview_file and now-last_preview>=.5:
                    prediction_age=capture_epoch-datetime.fromisoformat(health['last_prediction_at']).timestamp() if health.get('last_prediction_at') else float('inf')
                    current_probability=health.get('last_prediction') if prediction_age<2 and entry['valid_pose'] else None
                    preview=annotate(frame,points,current_probability)
                    preview=cv2.resize(preview,(640,round(preview.shape[0]*640/preview.shape[1])))
                    ok,encoded=cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,65])
                    if ok and len(encoded)<100000:
                        preview_path=Path(args.preview_file);temporary=preview_path.with_suffix('.tmp')
                        temporary.write_bytes(encoded.tobytes());os.replace(temporary,preview_path)
                    last_preview=now
                log.write(json.dumps(entry)+'\n')
                if args.snapshot and not saved and entry['valid_pose']:
                    cv2.imwrite(args.snapshot,annotate(frame,points,prediction['fall_probability'] if prediction else None));saved=True
                if frames%100==0:print(json.dumps({**health,**store.stats()}),flush=True)
    finally:
        cap.release();pose.close()
        for filename in (args.preview_file,args.status_file):
            if filename:Path(filename).unlink(missing_ok=True)
        if server:server.shutdown();server.server_close()
        print(json.dumps({'frames':frames,'predictions':predictions,'elapsed_s':time.perf_counter()-began,
                          **store.stats()}),flush=True)


if __name__=='__main__':main()
