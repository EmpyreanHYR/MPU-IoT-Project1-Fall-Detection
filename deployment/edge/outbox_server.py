"""Keep backlog available even while the camera/inference service is stopped."""
import argparse
import os
import signal
import threading
from edge_runtime import Store,start_api

parser=argparse.ArgumentParser()
parser.add_argument('--database',default='data/edge.sqlite3')
parser.add_argument('--bind',default=os.environ.get('FALLGUARD_RELAY_HOST','127.0.0.1'))
parser.add_argument('--port',type=int,default=18082)
args=parser.parse_args()
server=start_api(Store(args.database),args.bind,args.port,os.environ['FALLGUARD_INGEST_TOKEN'],
                 {'service':'persistent edge outbox'})
stop=threading.Event()
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
stop.wait();server.shutdown();server.server_close()
