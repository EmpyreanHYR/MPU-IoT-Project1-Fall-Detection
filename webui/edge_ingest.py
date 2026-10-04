"""Transactional, idempotent import of already-classified edge records."""
from datetime import datetime
from contextlib import closing
import json
import sqlite3
import uuid

SCHEMA='''CREATE TABLE IF NOT EXISTS edge_records (
    record_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
    captured_at TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL)'''
READING_FIELDS={'device_id','timestamp','frame_seq','edge_fps','network_rtt_ms',
                'fall_probability','pose_quality','keypoints','quality','model'}

def import_records(state,db_path,raw,validate_reading,utc_now):
    if not isinstance(raw,dict) or set(raw)!={'records'} or not isinstance(raw['records'],list) or not 1<=len(raw['records'])<=100:
        raise ValueError('records must contain 1 to 100 edge records')
    prepared=[]
    for item in raw['records']:
        if not isinstance(item,dict):raise ValueError('record must be an object')
        identifier=item.get('record_id')
        try:
            if str(uuid.UUID(identifier))!=identifier:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise ValueError('record_id must be a UUID')
        reading=validate_reading({k:v for k,v in item.items() if k in READING_FIELDS},source='edge_offline')
        stamp=datetime.fromisoformat(reading['timestamp'].replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('edge timestamp must include timezone')
        if item.get('alert_state') not in ('normal','suspected','confirmed','cleared'):
            raise ValueError('invalid edge alert state')
        transition=item.get('transition')
        if transition not in (None,'suspected','confirmed','cleared') or (transition and transition!=item['alert_state']):
            raise ValueError('invalid edge transition')
        payload=json.dumps(item,sort_keys=True,separators=(',',':'),allow_nan=False)
        prepared.append((identifier,item,reading,stamp.timestamp(),payload))
    received=utc_now();inserted=0;events=0
    with state.lock:
        with closing(sqlite3.connect(db_path,timeout=10)) as db, db:
            db.execute('PRAGMA synchronous=FULL');db.execute(SCHEMA);db.execute('BEGIN IMMEDIATE')
            for identifier,item,reading,epoch,payload in prepared:
                previous=db.execute('SELECT payload FROM edge_records WHERE record_id=?',(identifier,)).fetchone()
                if previous:
                    if previous[0]!=payload:raise ValueError('record_id already exists with a different payload')
                    continue
                db.execute('INSERT INTO edge_records VALUES(?,?,?,?,?)',
                    (identifier,reading['device_id'],reading['timestamp'],received,payload));inserted+=1
                if item.get('transition'):
                    db.execute('INSERT INTO events(device_id,timestamp,state,fall_probability,pose_quality,model,source) VALUES(?,?,?,?,?,?,?)',
                        (reading['device_id'],reading['timestamp'],item['transition'],reading['fall_probability'],reading['pose_quality'],reading['model'],'edge_offline'))
                    events+=1
        # Update display after commit. Backlog capture time determines freshness.
        for identifier,item,reading,epoch,payload in prepared:
            previous=state.devices.get(reading['device_id'],{})
            if epoch>=previous.get('last_received_epoch',0):
                state.devices[reading['device_id']]={**reading,'alert_state':item['alert_state'],
                    'last_received_epoch':epoch,'received_at':received,'pose_backend':item.get('pose_backend','unknown')}
    state.broadcast({'type':'snapshot','data':state.snapshot(10)})
    return {'record_ids':[x[0] for x in prepared],'inserted':inserted,'events_created':events}
