#!/usr/bin/env python3
"""Build offline presentation data from public aggregate evidence (stdlib only)."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
with (ROOT/'results/verification/verified_summary.csv').open(encoding='utf-8-sig',newline='') as stream:
    for row in csv.DictReader(stream):
        excluded = any(condition in row['group'] for condition in
                       ('/random_joint_drop/', '/lower_body_missing/'))
        status = 'excluded' if excluded else 'earlier_protocol' if row['suite']=='main' else 'current'
        reason = ('Zero filling before normalization also rescaled observed joints; excluded from current conclusions.'
                  if excluded else 'Separate earlier protocol; do not pool with the primary comparison.'
                  if status=='earlier_protocol' else '')
        rows.append(dict(suite=row['suite'],group=row['group'],metric=row['metric'],
                         mean=float(row['mean']),sd=float(row['sample_std']) if row['sample_std'] else None,
                         n=int(row['count']),status=status,exclusion_reason=reason))
content={'aggregates':rows,'edge':json.loads((ROOT/'results/edge/summary.json').read_text()),
         'alertReplay':json.loads((ROOT/'results/alert-replay/summary.json').read_text())}
(ROOT/'docs/assets/results-data.js').write_text('window.FALLGUARD_DATA = '+json.dumps(content,separators=(',',':'),allow_nan=False)+';\n')
with (ROOT/'docs/assets/aggregate-results.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['suite','group','metric','mean','sd','n','status','exclusion_reason'],lineterminator='\n');writer.writeheader();writer.writerows(rows)
print(f'Built {len(rows)} aggregate rows and public edge evidence.')
