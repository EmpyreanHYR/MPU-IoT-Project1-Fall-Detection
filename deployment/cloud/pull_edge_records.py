"""Pull durable edge records; acknowledge only after cloud commit."""
import json
import os
import time
from urllib.request import ProxyHandler,Request,build_opener

HTTP=build_opener(ProxyHandler({}))

def request(url,token,body=None):
    data=None if body is None else json.dumps(body,separators=(',',':')).encode()
    req=Request(url,data,{'X-Device-Token':token,'Content-Type':'application/json'})
    with HTTP.open(req,timeout=5) as response:return json.load(response)

def sync_once(edge_url,edge_token,cloud_url,cloud_token):
    pending=request(edge_url+'/records',edge_token)
    records=pending['records']
    if not records:return {'inserted':0,'pending_records':0}
    response=request(cloud_url+'/api/edge/records',cloud_token,{'records':records})
    ids=[r['record_id'] for r in records]
    if response.get('record_ids')!=ids:raise ValueError('cloud acknowledgement does not match submitted records')
    request(edge_url+'/ack',edge_token,{'record_ids':ids})
    return {**response,'pending_records':max(0,pending['pending_records']-len(ids))}

def main():
    edge=os.environ['FALLGUARD_EDGE_RECORDS_URL'].rstrip('/')
    edge_token=os.environ['FALLGUARD_EDGE_RECORDS_TOKEN'];cloud_token=os.environ['FALLGUARD_INGEST_TOKEN']
    cloud=os.environ.get('FALLGUARD_BACKEND_URL','http://127.0.0.1:18080').rstrip('/')
    previous_error=0
    while True:
        try:
            result=sync_once(edge,edge_token,cloud,cloud_token)
            if result['inserted'] or result.get('record_ids'):
                print(json.dumps({k:v for k,v in result.items() if k!='record_ids'}),flush=True)
            time.sleep(.05 if result['pending_records'] else .5)
        except Exception as exc:
            if time.monotonic()-previous_error>=30:
                print(f'Edge synchronization will retry: {type(exc).__name__}',flush=True);previous_error=time.monotonic()
            time.sleep(1)

if __name__=='__main__':main()
