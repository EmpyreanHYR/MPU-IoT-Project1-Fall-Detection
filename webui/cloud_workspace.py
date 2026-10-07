"""Cloud archive and private, authenticated edge dashboard bridge."""
from contextlib import closing
from datetime import datetime
import csv
import gzip
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import parse_qs,urlsplit
from urllib.request import Request,ProxyHandler,build_opener

BUILD='2026.10.07-cloud-demo1'
HTTP=build_opener(ProxyHandler({}))


class Workspace:
    def __init__(self,database,page,camera_request):
        self.database,self.page,self.camera_request=database,page,camera_request
        self.token=secrets.token_urlsafe(32)
        self.edge_url=os.environ.get('FALLGUARD_EDGE_RECORDS_URL','').rstrip('/')
        self.edge_token=os.environ.get('FALLGUARD_EDGE_RECORDS_TOKEN','')
        self.public_origin=os.environ.get('FALLGUARD_PUBLIC_ORIGIN','')
        self.camera_enabled=bool(os.environ.get('FALLGUARD_PI_RELAY_URL'))
        self.cache,self.cache_at={},0
        self.lock=threading.Lock()
    def edge(self):
        with self.lock:
            if time.monotonic()-self.cache_at<1.5:return self.cache
            self.cache={}
            if self.edge_url and self.edge_token:
                try:
                    req=Request(self.edge_url+'/dashboard/status',headers={'X-Device-Token':self.edge_token})
                    with HTTP.open(req,timeout=3) as response:self.cache=json.load(response)
                except (OSError,ValueError):pass
            self.cache_at=time.monotonic();return self.cache
    def query(self,query):
        clauses,values=[],[]
        state=query.get('state',[''])[0]
        if state:
            if state not in ('normal','suspected','confirmed','cleared'):raise ValueError('invalid state')
            clauses.append("json_extract(payload,'$.alert_state')=?");values.append(state)
        delivery=query.get('delivery',[''])[0]
        if delivery and delivery!='delivered':raise ValueError('Cloud archive contains received records only')
        for field,operator in [('from','>='),('to','<=')]:
            value=query.get(field,[''])[0]
            if value:
                datetime.fromisoformat(value.replace('Z','+00:00'))
                clauses.append(f'julianday(captured_at){operator}julianday(?)');values.append(value)
        return (' WHERE '+' AND '.join(clauses) if clauses else ''),values
    def records(self,query,export=False):
        where,values=self.query(query)
        limit=10000 if export else min(100,max(1,int(query.get('limit',['20'])[0])))
        offset=0 if export else max(0,int(query.get('offset',['0'])[0]))
        with closing(sqlite3.connect(self.database,timeout=2)) as db:
            total=db.execute('SELECT count(*) FROM edge_records'+where,values).fetchone()[0]
            rows=db.execute('SELECT payload,received_at FROM edge_records'+where+
                            ' ORDER BY julianday(captured_at) DESC,rowid DESC LIMIT ? OFFSET ?',[*values,limit,offset]).fetchall()
        items=[]
        for payload,received in rows:
            record=json.loads(payload)
            item={key:record.get(key) for key in ('timestamp','fall_probability','alert_state','device_id','record_id','transition')}
            item.update(delivered=True,received_at=received);items.append(item)
        return {'records':items,'total':total,'limit':limit,'offset':offset}
    def status(self):
        edge=self.edge();result={'build':BUILD,'server_time':time.time(),'runtime':edge.get('runtime',{}),
            'runtime_age_s':(edge['runtime_age_s']+max(0,time.monotonic()-self.cache_at) if isinstance(edge.get('runtime_age_s'),(int,float)) else None),'telemetry':edge.get('telemetry',{}),
            'pending_records':edge.get('pending_records'),'last_acknowledged':edge.get('last_acknowledged'),
            'edge_connected':bool(edge),'storage_available':False,'trend':[],'state_counts':{}}
        result['camera_control']={'enabled':self.camera_enabled and bool(edge),
                                 'state':edge.get('camera_control',{}).get('state','unknown')}
        try:
            with closing(sqlite3.connect(self.database,timeout=2)) as db:
                total,last_received=db.execute('SELECT count(*),max(received_at) FROM edge_records').fetchone()
                result.update(storage_available=True,total_records=total,last_cloud_received=last_received)
                result['state_counts']=dict(db.execute("SELECT json_extract(payload,'$.alert_state'),count(*) FROM edge_records GROUP BY 1"))
                rows=db.execute('SELECT payload FROM edge_records ORDER BY julianday(captured_at) DESC,rowid DESC LIMIT 120').fetchall()
                result['trend']=[{key:json.loads(row[0]).get(key) for key in ('timestamp','fall_probability','alert_state')} for row in reversed(rows)]
        except (sqlite3.Error,OSError):pass
        return result
    def send(self,handler,status,payload,content_type='application/json; charset=utf-8',filename=None):
        data=payload if isinstance(payload,bytes) else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
        compressed='gzip' in handler.headers.get('Accept-Encoding','') and len(data)>1024 and not content_type.startswith('image/')
        if compressed:data=gzip.compress(data,compresslevel=1)
        handler.send_response(status);handler.send_header('Content-Type',content_type)
        handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store')
        handler.send_header('Vary','Accept-Encoding');handler.send_header('X-Content-Type-Options','nosniff')
        if compressed:handler.send_header('Content-Encoding','gzip')
        if filename:handler.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        handler.end_headers()
        try:handler.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def get(self,handler):
        url=urlsplit(handler.path)
        if url.path not in ('/','/index.html','/api/workspace/status','/api/workspace/records','/api/workspace/export.csv','/api/workspace/preview'):return False
        try:
            if url.path in ('/','/index.html'):
                self.send(handler,200,self.page.read_text().replace('__CONTROL_TOKEN__',self.token).encode(),'text/html; charset=utf-8')
            elif url.path=='/api/workspace/status':self.send(handler,200,self.status())
            elif url.path=='/api/workspace/preview':
                if not self.edge_url or not self.edge_token:raise OSError('edge not configured')
                req=Request(self.edge_url+'/dashboard/preview',headers={'X-Device-Token':self.edge_token})
                with HTTP.open(req,timeout=4) as response:
                    data=response.read(256001)
                    if len(data)>256000 or not data.startswith(b'\xff\xd8'):raise ValueError('invalid preview')
                    self.send(handler,200,data,'image/jpeg')
            else:
                exporting=url.path.endswith('.csv');data=self.records(parse_qs(url.query),exporting)
                if exporting:
                    out=io.StringIO();writer=csv.writer(out);writer.writerow(['capture_time','device','fall_probability','alert_state','delivery','record_id','cloud_received_at'])
                    def safe(value):
                        text='' if value is None else str(value)
                        return "'"+text if text.startswith(('=','+','-','@','\t','\r','\n')) else text
                    for item in data['records']:
                        writer.writerow([safe(item['timestamp']),safe(item['device_id']),safe(item['fall_probability']),safe(item['alert_state']),'received',safe(item['record_id']),safe(item['received_at'])])
                    self.send(handler,200,('\ufeff'+out.getvalue()).encode(),'text/csv; charset=utf-8','fallguard-cloud-records.csv')
                else:self.send(handler,200,data)
        except (ValueError,TypeError):self.send(handler,400,{'error':'查询参数不正确'})
        except (OSError,sqlite3.Error):self.send(handler,503,{'error':'数据暂不可用，云端历史记录仍保留'})
        return True
    def post(self,handler):
        if urlsplit(handler.path).path!='/api/workspace/camera':return False
        origin=self.public_origin or ('http://'+handler.headers.get('Host',''))
        if (handler.headers.get('Origin')!=origin or
            handler.headers.get('Content-Type','').split(';')[0]!='application/json' or
            not secrets.compare_digest(handler.headers.get('X-Control-Token',''),self.token)):
            self.send(handler,403,{'error':'控制请求未授权'});return True
        try:
            data=handler.read_json(1024)
            if not isinstance(data,dict) or data.get('action') not in ('start','stop') or not self.camera_enabled:raise ValueError
            status,payload=self.camera_request(data['action'],'cloud-workspace-session')
            self.cache_at=0
            self.send(handler,status,{'state':'active' if payload.get('running') else 'inactive','error':payload.get('error')})
        except ValueError:self.send(handler,400,{'error':'控制操作不可用或参数不正确'})
        return True
