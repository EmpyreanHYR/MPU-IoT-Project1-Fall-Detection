#!/usr/bin/env python3
"""Verify the published deployment assets without importing ML libraries."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/"artifacts/models/manifest.json").read_text())
for asset in manifest["files"]:
    path=ROOT/asset["path"]
    if path.stat().st_size != asset["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest()!=asset["sha256"]:
        raise SystemExit(f"Asset verification failed: {asset['path']}")
    print(f"Verified: {asset['path']}")
