"""Start all real local services, deliver one fixture, then verify clean shutdown."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"deployment/edge"))
from edge_runtime import Store,utc


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


class LauncherTests(unittest.TestCase):
    def test_local_process_delivery_and_shutdown(self):
        ports=set()
        while len(ports)<3:ports.add(port())
        cloud,edge,dashboard=ports
        env={k:v for k,v in os.environ.items() if not k.startswith("FALLGUARD_")}
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp)/"services.log").open("w+") as log:
                process=subprocess.Popen([sys.executable,str(ROOT/"scripts/run_deployment.py"),
                    "--data-dir",tmp,"--cloud-port",str(cloud),"--edge-port",str(edge),
                    "--dashboard-port",str(dashboard)],env=env,stdout=log,stderr=log)
                try:
                    ready=False
                    for _ in range(100):
                        if process.poll() is not None:break
                        try:
                            with urlopen(f"http://127.0.0.1:{dashboard}/api/status",timeout=.2) as response:
                                ready=response.status==200
                            if ready:break
                        except OSError:time.sleep(.1)
                    log.flush();log.seek(0)
                    self.assertTrue(ready,log.read())
                    store=Store(Path(tmp)/"edge.sqlite3")
                    record=store.add(dict(device_id="launcher-fixture",timestamp=utc(),frame_seq=1,
                        fall_probability=.9,pose_quality=.8,model="synthetic software fixture"))
                    for _ in range(100):
                        if store.stats()["pending_records"]==0:break
                        time.sleep(.1)
                    self.assertEqual(store.stats()["pending_records"],0)
                    with urlopen(f"http://127.0.0.1:{cloud}/api/events",timeout=2) as response:
                        events=json.load(response)
                    self.assertEqual(events[0]["timestamp"],record["timestamp"])
                    with urlopen(f"http://127.0.0.1:{cloud}/",timeout=2) as response:
                        self.assertIn(b"FallGuard",response.read())
                    with urlopen(f"http://127.0.0.1:{cloud}/api/workspace/status",timeout=5) as response:
                        workspace=json.load(response)
                    self.assertTrue(workspace["edge_connected"])
                    self.assertEqual(workspace["total_records"],1)
                    self.assertEqual(workspace["pending_records"],0)
                    with urlopen(f"http://127.0.0.1:{cloud}/api/workspace/records",timeout=2) as response:
                        archive=json.load(response)
                    self.assertEqual(archive["records"][0]["record_id"],record["record_id"])
                finally:
                    process.terminate();process.wait(timeout=15)
                self.assertEqual(process.returncode,0)
        for p in ports:
            with socket.socket() as sock:
                self.assertNotEqual(sock.connect_ex(("127.0.0.1",p)),0)


if __name__=="__main__":unittest.main()
