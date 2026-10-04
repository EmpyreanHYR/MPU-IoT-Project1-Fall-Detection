"""Read-only localhost dashboard for the existing offline inference service."""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit


def snapshot(status_file, database):
    result = {'runtime': {}, 'runtime_age_s': None, 'records': [], 'storage_available': False}
    try:
        result['runtime'] = json.loads(status_file.read_text())
        result['runtime_age_s'] = max(0, time.time() - status_file.stat().st_mtime)
    except (OSError, ValueError):
        pass
    try:
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
            total, pending, acknowledged = db.execute(
                'SELECT count(*),sum(acknowledged IS NULL),max(acknowledged) FROM outbox').fetchone()
            result.update(storage_available=True, total_records=total,
                          pending_records=pending or 0, last_acknowledged=acknowledged)
            rows = db.execute('SELECT payload,acknowledged FROM outbox ORDER BY seq DESC LIMIT 6').fetchall()
            for payload, ack in rows:
                record = json.loads(payload)
                result['records'].append({key: record.get(key) for key in
                    ('timestamp', 'fall_probability', 'alert_state', 'device_id')})
                result['records'][-1]['delivered'] = ack is not None
    except (sqlite3.Error, ValueError, OSError):
        pass
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18300)
    parser.add_argument('--status', type=Path, default=Path('data/status.json'))
    parser.add_argument('--preview', type=Path, default=Path('data/preview.jpg'))
    parser.add_argument('--database', type=Path, default=Path('data/edge.sqlite3'))
    args = parser.parse_args()
    page = Path(__file__).with_name('local_dashboard.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == '/':
                data, content_type = page, 'text/html; charset=utf-8'
            elif path == '/api/status':
                data = json.dumps(snapshot(args.status, args.database), ensure_ascii=False).encode()
                content_type = 'application/json; charset=utf-8'
            elif path == '/preview.jpg':
                try:
                    if time.time() - args.preview.stat().st_mtime > 5:
                        raise FileNotFoundError
                    data = args.preview.read_bytes()
                except OSError:
                    self.send_error(503, 'Camera preview unavailable')
                    return
                content_type = 'image/jpeg'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(data)

    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
