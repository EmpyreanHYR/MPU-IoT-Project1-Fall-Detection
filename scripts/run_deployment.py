#!/usr/bin/env python3
"""Start local, edge-only or cloud-only services and stop all child processes together."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["local", "edge", "cloud"], default="local")
    parser.add_argument("--data-dir", type=Path, default=ROOT/"data/local-deployment")
    parser.add_argument("--source", help="Optional camera number or local video; absent means records/dashboard only")
    parser.add_argument("--backend", choices=["cpu", "hailo", "auto"], default="cpu")
    parser.add_argument("--cpu-model", type=Path)
    parser.add_argument("--hef", type=Path, default=Path("/usr/share/hailo-models/yolov8s_pose_h10.hef"))
    parser.add_argument("--device-id", default="local-edge-01")
    parser.add_argument("--cloud-port", type=int, default=18080)
    parser.add_argument("--edge-port", type=int, default=18082)
    parser.add_argument("--dashboard-port", type=int, default=18300)
    args = parser.parse_args()
    if len({args.cloud_port,args.edge_port,args.dashboard_port}) != 3:
        parser.error("Use distinct service ports")
    if args.mode != "local" and not os.environ.get("FALLGUARD_INGEST_TOKEN"):
        parser.error("Set FALLGUARD_INGEST_TOKEN for separate-host services")
    if args.source is not None:
        if args.mode == "cloud":
            parser.error("A camera/video source belongs to edge or local mode")
        if args.backend in ("cpu", "auto") and (args.cpu_model is None or not args.cpu_model.is_file()):
            parser.error("CPU/auto inference requires --cpu-model pointing to an exported YOLOv8 pose ONNX")
        if args.backend == "hailo" and not args.hef.is_file():
            parser.error("Hailo inference requires a locally installed compatible HEF")
    data = args.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    edge = ROOT/"deployment/edge"
    common = os.environ.copy()
    common["FALLGUARD_INGEST_TOKEN"] = common.get("FALLGUARD_INGEST_TOKEN") or secrets.token_urlsafe(32)
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    def start(script, *arguments, env=None):
        process = subprocess.Popen([sys.executable, str(script), *map(str,arguments)],
                                   cwd=ROOT, env=env or common)
        children.append(process)
        return process

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    failed = False
    try:
        if args.mode in ("local", "cloud"):
            cloud_env = {**common, "FALLGUARD_HOST":"127.0.0.1",
                         "FALLGUARD_PORT":str(args.cloud_port), "FALLGUARD_DATA_DIR":str(data/"cloud")}
            start(ROOT/"webui/server.py", env=cloud_env)
            ready = False
            for _ in range(100):
                if stopping or any(p.poll() is not None for p in children):
                    break
                try:
                    with urlopen(f"http://127.0.0.1:{args.cloud_port}/api/health", timeout=.2) as response:
                        ready = response.status == 200
                    if ready: break
                except OSError:
                    time.sleep(.05)
            if not ready: raise RuntimeError("Cloud service did not become ready")
            print(f"Cloud dashboard: http://127.0.0.1:{args.cloud_port}", flush=True)
        if args.mode in ("local", "edge"):
            db = data/"edge.sqlite3"
            start(edge/"outbox_server.py", "--database", db, "--bind", common.get("FALLGUARD_RELAY_HOST","127.0.0.1"),
                  "--port", args.edge_port)
            if args.source is not None:
                options = ["--source",args.source,"--backend",args.backend,"--hef",args.hef,
                    "--classifier",ROOT/"artifacts/models/masked_bimamba_quality.onnx",
                    "--database",db,"--device-id",args.device_id,"--no-api",
                    "--log",data/"runtime.jsonl","--status-file",data/"status.json",
                    "--preview-file",data/"preview.jpg"]
                if args.cpu_model: options += ["--cpu-model",args.cpu_model.resolve()]
                start(edge/"edge_runtime.py", *options)
            start(edge/"local_dashboard.py", "--database", db, "--port",args.dashboard_port,
                  "--status",data/"status.json","--preview",data/"preview.jpg")
            print(f"Local edge dashboard: http://127.0.0.1:{args.dashboard_port}", flush=True)
        if args.mode == "local":
            sync_env = {**common, "FALLGUARD_EDGE_RECORDS_URL":f"http://127.0.0.1:{args.edge_port}",
                "FALLGUARD_EDGE_RECORDS_TOKEN":common["FALLGUARD_INGEST_TOKEN"],
                "FALLGUARD_BACKEND_URL":f"http://127.0.0.1:{args.cloud_port}"}
            start(ROOT/"deployment/cloud/pull_edge_records.py", env=sync_env)
        elif args.mode == "cloud" and common.get("FALLGUARD_EDGE_RECORDS_URL"):
            sync_env = {**common,"FALLGUARD_BACKEND_URL":f"http://127.0.0.1:{args.cloud_port}"}
            if not sync_env.get("FALLGUARD_EDGE_RECORDS_TOKEN"):
                raise ValueError("Set FALLGUARD_EDGE_RECORDS_TOKEN to enable edge pulling")
            start(ROOT/"deployment/cloud/pull_edge_records.py", env=sync_env)
        if args.mode != "cloud" and args.source is None:
            print("Camera inference is stopped. Add --source and pose-model arguments to enable it.",flush=True)
        while not stopping:
            if any(process.poll() is not None for process in children):
                failed = any(process.returncode not in (None,0) for process in children)
                break
            time.sleep(.1)
    finally:
        for process in reversed(children):
            if process.poll() is None: process.terminate()
        for process in children:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
    if failed: raise SystemExit(1)


if __name__ == "__main__":
    main()
