"""Local edge dashboard: read-only records and optional user-service control."""
from __future__ import annotations
from contextlib import contextmanager
import argparse
import csv
import gzip
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

BUILD = '2026.10.07'
STATES = {'normal', 'suspected', 'confirmed', 'cleared'}
FIELDS = ('timestamp', 'fall_probability', 'alert_state', 'device_id', 'record_id', 'transition')


@contextmanager
def connect(database):
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    try: yield db
    finally: db.close()


def filters(query):
    clauses, values = [], []
    state = query.get('state', [''])[0]
    delivery = query.get('delivery', [''])[0]
    if state:
        if state not in STATES: raise ValueError('invalid state')
        clauses.append("json_extract(payload,'$.alert_state')=?"); values.append(state)
    if delivery:
        if delivery not in ('pending', 'delivered'): raise ValueError('invalid delivery')
        clauses.append('acknowledged IS ' + ('NULL' if delivery == 'pending' else 'NOT NULL'))
    for field, operator in (('from', '>='), ('to', '<=')):
        value = query.get(field, [''])[0]
        if value:
            from datetime import datetime
            try: datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError: raise ValueError('invalid date')
            clauses.append(f"julianday(json_extract(payload,'$.timestamp')){operator}julianday(?)")
            values.append(value)
    return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), values


def records(database, query, export=False):
    where, values = filters(query)
    limit = 10000 if export else min(100, max(1, int(query.get('limit', ['20'])[0])))
    offset = 0 if export else max(0, int(query.get('offset', ['0'])[0]))
    with connect(database) as db:
        total = db.execute('SELECT count(*) FROM outbox' + where, values).fetchone()[0]
        rows = db.execute('SELECT payload,acknowledged FROM outbox' + where +
                          ' ORDER BY seq DESC LIMIT ? OFFSET ?', [*values, limit, offset]).fetchall()
    items = []
    for payload, ack in rows:
        record = json.loads(payload)
        item = {key: record.get(key) for key in FIELDS}
        item.update(delivered=ack is not None, acknowledged_at=ack)
        items.append(item)
    return {'records': items, 'total': total, 'limit': limit, 'offset': offset}


def telemetry(database):
    info = {'disk_free_bytes': None, 'disk_total_bytes': None, 'cpu_temperature_c': None,
            'memory_available_bytes': None, 'memory_total_bytes': None, 'load_1m': None}
    try:
        usage = shutil.disk_usage(database.parent)
        info.update(disk_free_bytes=usage.free, disk_total_bytes=usage.total)
    except OSError: pass
    try: info['cpu_temperature_c'] = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
    except (OSError, ValueError): pass
    try:
        memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        info['memory_available_bytes'] = int(memory['MemAvailable'].split()[0]) * 1024
        info['memory_total_bytes'] = int(memory['MemTotal'].split()[0]) * 1024
    except (OSError, KeyError, ValueError): pass
    try: info['load_1m'] = os.getloadavg()[0]
    except (OSError, AttributeError): pass
    return info


def snapshot(status_file, database):
    result = {'runtime': {}, 'runtime_age_s': None, 'records': [], 'storage_available': False,
              'build': BUILD, 'server_time': time.time(), 'telemetry': telemetry(database), 'trend': []}
    try:
        result['runtime'] = json.loads(status_file.read_text())
        result['runtime_age_s'] = max(0, time.time() - status_file.stat().st_mtime)
    except (OSError, ValueError): pass
    try:
        with connect(database) as db:
            total, pending, acknowledged = db.execute(
                'SELECT count(*),sum(acknowledged IS NULL),max(acknowledged) FROM outbox').fetchone()
            result.update(storage_available=True, total_records=total,
                          pending_records=pending or 0, last_acknowledged=acknowledged)
            counts = db.execute("SELECT json_extract(payload,'$.alert_state'),count(*) FROM outbox GROUP BY 1").fetchall()
            result['state_counts'] = dict(counts)
            rows = db.execute('SELECT payload,acknowledged FROM outbox ORDER BY seq DESC LIMIT 120').fetchall()
            for i, (payload, ack) in enumerate(rows):
                record = json.loads(payload)
                if i < 6:
                    result['records'].append({**{key: record.get(key) for key in FIELDS}, 'delivered': ack is not None})
                result['trend'].append({key: record.get(key) for key in ('timestamp', 'fall_probability', 'alert_state')})
            result['trend'].reverse()
    except (sqlite3.Error, ValueError, OSError): pass
    return result


class CameraControl:
    def __init__(self, service):
        self.service, self.cached, self.checked = service, 'unknown', 0
    def state(self, force=False):
        if not self.service: return {'enabled': False, 'state': 'unmanaged'}
        if force or time.monotonic() - self.checked > 3:
            try:
                result = subprocess.run(['/usr/bin/systemctl', '--user', 'is-active', self.service],
                                        capture_output=True, text=True, timeout=3)
                self.cached = result.stdout.strip() or 'unknown'
            except (OSError, subprocess.TimeoutExpired): self.cached = 'unknown'
            self.checked = time.monotonic()
        return {'enabled': True, 'state': self.cached}
    def action(self, action):
        if not self.service: raise ValueError('camera control unavailable')
        if action not in ('start', 'stop'): raise ValueError('invalid action')
        subprocess.run(['/usr/bin/systemctl', '--user', action, self.service],
                       capture_output=True, timeout=15, check=True)
        return self.state(force=True)


class Preview:
    """Resize a volatile JPEG for display, caching the latest source frame only."""
    def __init__(self, path):
        self.path, self.stamp, self.data = path, None, None
        self.lock = threading.Lock()
    def read(self):
        with self.lock:
            stat = self.path.stat()
            if time.time() - stat.st_mtime > 5: raise FileNotFoundError
            if stat.st_mtime_ns != self.stamp:
                data = self.path.read_bytes()
                try:
                    import cv2
                    import numpy as np
                    cv2.setNumThreads(1)
                    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is not None:
                        height, width = image.shape[:2]
                        if width > 960:
                            image = cv2.resize(image, (960, max(1, round(height*960/width))), interpolation=cv2.INTER_AREA)
                        ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ok: data = encoded.tobytes()
                except ImportError: pass
                self.data, self.stamp = data, stat.st_mtime_ns
            return self.data


def make_server(args):
    token = secrets.token_urlsafe(32)
    page = Path(__file__).with_name('local_dashboard.html').read_text().replace('__CONTROL_TOKEN__', token).encode()
    control = CameraControl(args.camera_service)
    preview = Preview(args.preview)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def local(self):
            # Restrict Host, including the port, to resist DNS rebinding.
            if self.headers.get('Host', '') not in (f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'):
                self.send_error(403); return False
            return True
        def reply(self, code, data, content_type='application/json; charset=utf-8', attachment=None):
            if not isinstance(data, bytes): data = json.dumps(data, ensure_ascii=False).encode()
            compressed = 'gzip' in self.headers.get('Accept-Encoding', '') and len(data) > 1024 and not content_type.startswith('image/')
            if compressed: data = gzip.compress(data, compresslevel=1)
            self.send_response(code)
            if compressed: self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            if attachment: self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
            self.end_headers()
            try: self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError): pass
        def do_GET(self):
            if not self.local(): return
            url = urlsplit(self.path)
            try:
                if url.path == '/': self.reply(200, page, 'text/html; charset=utf-8')
                elif url.path == '/api/status':
                    data = snapshot(args.status, args.database); data['camera_control'] = control.state()
                    self.reply(200, data)
                elif url.path in ('/api/records', '/api/export.csv'):
                    data = records(args.database, parse_qs(url.query), export=url.path.endswith('.csv'))
                    if url.path.endswith('.csv'):
                        out = io.StringIO(); writer = csv.writer(out)
                        writer.writerow(['capture_time', 'device', 'fall_probability', 'alert_state', 'delivery', 'record_id'])
                        for row in data['records']:
                            def safe(value):
                                value = '' if value is None else str(value)
                                return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
                            writer.writerow([safe(row['timestamp']), safe(row['device_id']), safe(row['fall_probability']),
                                             safe(row['alert_state']), 'delivered' if row['delivered'] else 'pending', safe(row['record_id'])])
                        self.reply(200, ('\ufeff'+out.getvalue()).encode(), 'text/csv; charset=utf-8', 'fallguard-records.csv')
                    else: self.reply(200, data)
                elif url.path == '/preview.jpg':
                    self.reply(200, preview.read(), 'image/jpeg')
                else: self.send_error(404)
            except (ValueError, TypeError): self.reply(400, {'error': '查询参数不正确'})
            except (sqlite3.Error, OSError): self.reply(503, {'error': '本地数据暂不可用'})
        def do_POST(self):
            if not self.local(): return
            expected = 'http://' + self.headers['Host']
            if (self.headers.get('Origin') != expected or
                self.headers.get('Content-Type', '').split(';')[0] != 'application/json' or
                not secrets.compare_digest(self.headers.get('X-Control-Token', ''), token)):
                self.reply(403, {'error': '控制请求未授权'}); return
            if urlsplit(self.path).path != '/api/camera': self.send_error(404); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 1024: raise ValueError
                data = json.loads(self.rfile.read(size))
                self.reply(200, control.action(data['action']))
            except (ValueError, KeyError, TypeError): self.reply(400, {'error': '控制操作不可用或参数不正确'})
            except (OSError, subprocess.SubprocessError): self.reply(503, {'error': '操作未完成，请检查检测服务'})
    return ThreadingHTTPServer(('127.0.0.1', args.port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18300)
    parser.add_argument('--status', type=Path, default=Path('data/status.json'))
    parser.add_argument('--preview', type=Path, default=Path('data/preview.jpg'))
    parser.add_argument('--database', type=Path, default=Path('data/edge.sqlite3'))
    parser.add_argument('--camera-service', choices=['fallguard-camera.service'], default=None,
                        help='Enable localhost-only control of the existing Pi user service')
    make_server(parser.parse_args()).serve_forever()


if __name__ == '__main__': main()
