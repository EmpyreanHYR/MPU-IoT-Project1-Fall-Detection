#!/usr/bin/env python3
"""Build or check the deterministic deployed-source/document release manifest."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'deployment/release-manifest.json'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
paths=[]
for folder,extensions in [('deployment/edge',{'.py','.html'}),('deployment/cloud',{'.py'}),
                          ('deployment/systemd',{'.service'}),('deployment/config',{'.example'}),
                          ('webui',{'.py','.html','.js','.css'}),
                          ('docs/downloads',{'.pdf'}),('manuscripts/final-report',{'.tex'}),
                          ('documentation/zh',{'.md'})]:
    paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in extensions)
paths.extend([ROOT/'deployment/cloud/pull_edge_records.py',ROOT/'scripts/run_deployment.py',
              ROOT/'artifacts/models/masked_bimamba_quality.onnx',ROOT/'artifacts/models/masked_bimamba.pt'])
manifest={'release':'2026.10.07-demo1','edge_build':'2026.10.07','cloud_build':'2026.10.07-cloud-demo1',
          'files':[{ 'path':str(p.relative_to(ROOT)), 'bytes':p.stat().st_size,
                     'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in sorted(set(paths))]}
text=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
if args.check:
    if not TARGET.is_file() or TARGET.read_text()!=text:
        raise SystemExit('Release manifest differs: run scripts/build_release_manifest.py after updating files')
    print(f'Verified release source and documents: {len(manifest["files"])} files')
else:
    TARGET.write_text(text)
    print(f'Built release manifest: {len(manifest["files"])} files')
