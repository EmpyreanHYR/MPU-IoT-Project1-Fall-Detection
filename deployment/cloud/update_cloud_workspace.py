"""Install a verified workspace package on the existing Tencent FallGuard VM."""
from contextlib import closing
from datetime import datetime
import grp
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from urllib.request import urlopen

root=Path('/root/跌倒检测/webui')
package=Path(__file__).resolve().parent
manifest=json.loads((package/'manifest.json').read_text())
for name,expected in manifest.items():
    source=package/name
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise RuntimeError('Package checksum mismatch: '+name)
    if name.endswith('.py'):compile(source.read_text(),name,'exec')
backup=root/'backups'/('workspace-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True,mode=0o700)
dropin=Path('/etc/systemd/system/fallguard.service.d/workspace.conf')
for name in manifest:
    source=root/name
    if source.exists():
        target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
if dropin.exists():shutil.copy2(dropin,backup/'workspace.conf')
if (root/'data/events.sqlite3').exists():
    with closing(sqlite3.connect(root/'data/events.sqlite3')) as db,closing(sqlite3.connect(backup/'events.sqlite3')) as dest:db.backup(dest)
print(json.dumps({'backup':str(backup),'verified_files':len(manifest)}),flush=True)
subprocess.run(['systemctl','stop','fallguard-edge-sync.service'],check=True)
try:
    for name in manifest:
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_name(dest.name+'.next');shutil.copyfile(package/name,temp)
        shutil.chown(temp,user='root',group='fallguard');temp.chmod(0o644);temp.replace(dest)
    dropin.parent.mkdir(parents=True,exist_ok=True)
    dropin.write_text('[Service]\nEnvironmentFile=/etc/fallguard-edge-sync.env\nEnvironment=FALLGUARD_PUBLIC_ORIGIN=https://159.75.68.253:2622\n')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','restart','fallguard.service'],check=True)
    ready=False
    for _ in range(20):
        try:
            with urlopen('http://127.0.0.1:18080/api/health',timeout=2) as response:health=json.load(response)
            if health.get('build')=='2026.10.07-cloud':ready=True;break
        except OSError:pass
        time.sleep(.5)
    if not ready:raise RuntimeError('Updated application did not become ready')
    subprocess.run(['systemctl','start','fallguard-public.service','fallguard-edge-sync.service'],check=True)
    with urlopen('http://127.0.0.1:18080/api/workspace/status',timeout=8) as response:status=json.load(response)
    if not status.get('storage_available'):raise RuntimeError('Cloud archive is unavailable')
    print(json.dumps({'updated':True,'build':health['build'],'edge_connected':status['edge_connected'],
                      'cloud_records':status['total_records'],'pending_records':status['pending_records']}),flush=True)
except Exception:
    for name in manifest:
        source=backup/name
        if source.exists():shutil.copy2(source,root/name)
        elif (root/name).exists():(root/name).unlink()
    if (backup/'workspace.conf').exists():shutil.copy2(backup/'workspace.conf',dropin)
    elif dropin.exists():dropin.unlink()
    subprocess.run(['systemctl','daemon-reload'])
    subprocess.run(['systemctl','restart','fallguard.service'])
    subprocess.run(['systemctl','start','fallguard-public.service','fallguard-edge-sync.service'])
    print('Update failed; original application files restored. Live database retained.',flush=True)
    raise
