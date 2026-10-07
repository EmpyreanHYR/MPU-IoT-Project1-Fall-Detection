"""Dashboard backend and durable cloud ingestion for FallGuard.

The classifier is an upstream component. This service accepts its probability and
anonymous pose, runs a repeated-reading alert state machine, persists transitions,
and streams current state to the bilingual dashboard.
"""

from __future__ import annotations

import hmac
import base64
import binascii
import json
import math
import os
import queue
import random
import re
import sqlite3
import threading
import time
from collections import deque
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import ProxyHandler, Request, build_opener
from urllib.error import HTTPError, URLError
from edge_ingest import import_records, SCHEMA, READING_FIELDS
from cloud_workspace import Workspace, BUILD

# The public deployment classifies on the edge. Historical cloud inference
# endpoints return an explicit unavailable response.

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("FALLGUARD_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "events.sqlite3"
HOST = os.environ.get("FALLGUARD_HOST", "127.0.0.1")
PORT = int(os.environ.get("FALLGUARD_PORT", "8080"))
INGEST_TOKEN = os.environ.get("FALLGUARD_INGEST_TOKEN", "")
DASHBOARD_USER = os.environ.get("FALLGUARD_DASHBOARD_USER", "")
DASHBOARD_PASSWORD = os.environ.get("FALLGUARD_DASHBOARD_PASSWORD", "")
PI_RELAY_URL = os.environ.get("FALLGUARD_PI_RELAY_URL", "").rstrip("/")
CAMERA_PASSWORD = os.environ.get("FALLGUARD_CAMERA_PASSWORD", "")
DIRECT_HTTP = build_opener(ProxyHandler({}))
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CAMERA_CLIENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,80}$")
CAMERA_CONTROL_LOCK = threading.RLock()
CAMERA_LEASE: dict | None = None
CAMERA_AUTH_FAILURES: deque[float] = deque()
PI_STATUS_CACHE: tuple[int, dict] | None = None
PI_STATUS_CACHE_AT = 0.0
PI_FRAME_CACHE: tuple[float, bytes] | None = None
PI_FRAME_LOCK = threading.Lock()
DEMO_DEVICE = "demo-pi5-01"

CLOUD_MODEL_ERROR = "Offline edge mode: classification runs on the device."


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _pi_relay_request(action: str) -> tuple[int, dict]:
    attempts = 2 if action == "status" else 1
    for attempt in range(attempts):
        request = Request(f"{PI_RELAY_URL}/camera/{action}", method="GET" if action == "status" else "POST")
        try:
            with DIRECT_HTTP.open(request, timeout=18 if action != "status" else 8) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return 502, {"connected": False, "running": False, "state": "error", "error": f"Pi camera service returned HTTP {exc.code} / 树莓派摄像头服务返回错误"}
        except (URLError, TimeoutError, OSError, ValueError):
            if attempt + 1 < attempts:
                time.sleep(0.4)
    return 503, {"connected": False, "running": False, "state": "offline", "error": "Raspberry Pi is unreachable / 无法连接树莓派"}


def _pi_status_request(force: bool = False) -> tuple[int, dict]:
    global PI_STATUS_CACHE, PI_STATUS_CACHE_AT
    if not force and PI_STATUS_CACHE is not None and time.time() - PI_STATUS_CACHE_AT < 5:
        return PI_STATUS_CACHE
    PI_STATUS_CACHE = _pi_relay_request("status")
    PI_STATUS_CACHE_AT = time.time()
    return PI_STATUS_CACHE


def _camera_public_status(payload: dict, client_id: str) -> dict:
    global CAMERA_LEASE
    running = bool(payload.get("running"))
    if not running:
        CAMERA_LEASE = None
    return {
        **payload,
        "in_use": running,
        "availability": "owned" if running else "available",
        "owned_by_requester": running,
        "started_at": CAMERA_LEASE.get("started_at") if CAMERA_LEASE else None,
    }


def pi_camera_request(action: str, client_id: str, password: str = "") -> tuple[int, dict]:
    global CAMERA_LEASE, PI_STATUS_CACHE, PI_STATUS_CACHE_AT, PI_FRAME_CACHE
    if not PI_RELAY_URL:
        return 503, {"connected": False, "running": False, "state": "unconfigured", "error": "Raspberry Pi connection is not configured / 尚未配置树莓派连接"}
    if not CAMERA_CLIENT_PATTERN.fullmatch(client_id):
        return 400, {"connected": False, "running": False, "state": "invalid", "error": "Invalid camera session / 摄像头会话无效"}
    with CAMERA_CONTROL_LOCK:
        status, current = _pi_status_request(force=action != "status")
        if status != 200:
            return status, current
        current = _camera_public_status(current, client_id)
        if action == "status":
            return 200, current
        if action == "start":
            if current["running"]:
                return 200, _camera_public_status(current, client_id)
        status, payload = _pi_relay_request(action)
        if status != 200:
            return status, payload
        PI_STATUS_CACHE = (status, payload)
        PI_STATUS_CACHE_AT = time.time()
        CAMERA_LEASE = {"client_id": client_id, "started_at": time.time(), "last_seen": time.time()} if action == "start" else None
        if action == "stop":
            PI_FRAME_CACHE = None
        return 200, _camera_public_status(payload, client_id)


def pi_camera_frame() -> tuple[int, bytes | dict]:
    global PI_FRAME_CACHE
    if not PI_RELAY_URL:
        return 503, {"error": "Raspberry Pi connection is not configured / 尚未配置树莓派连接"}
    now = time.monotonic()
    if PI_FRAME_CACHE is not None and now - PI_FRAME_CACHE[0] < 0.8:
        return 200, PI_FRAME_CACHE[1]
    with PI_FRAME_LOCK:
        now = time.monotonic()
        if PI_FRAME_CACHE is not None and now - PI_FRAME_CACHE[0] < 0.8:
            return 200, PI_FRAME_CACHE[1]
        try:
            with DIRECT_HTTP.open(Request(f"{PI_RELAY_URL}/camera/frame", method="GET"), timeout=6) as response:
                if response.status == 204:
                    return 204, b""
                frame = response.read(100_001)
                if response.status != 200 or response.headers.get_content_type() != "image/jpeg" or not frame.startswith(b"\xff\xd8") or len(frame) > 100_000:
                    return 502, {"error": "Invalid Raspberry Pi camera frame / 树莓派摄像头画面无效"}
                PI_FRAME_CACHE = (time.monotonic(), frame)
                return 200, frame
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return 503, {"error": "Raspberry Pi preview is unavailable / 树莓派预览不可用"}


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def validate_reading(raw: object, source: str = "live") -> dict:
    if not isinstance(raw, dict):
        raise ValueError("JSON object required")
    allowed = {"device_id", "timestamp", "frame_seq", "edge_fps", "network_rtt_ms", "fall_probability", "pose_quality", "keypoints", "quality", "branch_scores", "model"}
    unexpected = set(raw) - allowed
    if unexpected:
        raise ValueError("unsupported fields: " + ", ".join(sorted(map(str, unexpected))))
    device_id = raw.get("device_id")
    if not isinstance(device_id, str) or not DEVICE_ID_PATTERN.fullmatch(device_id):
        raise ValueError("device_id must be a short device identifier")
    probability = number(raw.get("fall_probability"), "fall_probability", 0, 1)
    edge_fps = number(raw.get("edge_fps", 0), "edge_fps", 0, 240)
    network_rtt_ms = number(raw.get("network_rtt_ms", 0), "network_rtt_ms", 0, 60000)
    frame_seq = raw.get("frame_seq", 0)
    if isinstance(frame_seq, bool) or not isinstance(frame_seq, int) or not 0 <= frame_seq <= 2**53:
        raise ValueError("frame_seq must be a nonnegative integer")
    model = raw.get("model", "unspecified")
    if not isinstance(model, str) or len(model) > 80:
        raise ValueError("model must be a short string")
    keypoints = raw.get("keypoints", [])
    if not isinstance(keypoints, list) or len(keypoints) not in (0, 17):
        raise ValueError("keypoints must contain 17 COCO points or be empty")
    clean_points = []
    for index, point in enumerate(keypoints):
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError(f"keypoints[{index}] must be [x, y, confidence]")
        clean_points.append([number(v, f"keypoints[{index}]", 0, 1) for v in point])
    quality_raw = raw.get("quality", {})
    if not isinstance(quality_raw, dict):
        raise ValueError("quality must be an object")
    quality = {
        key: number(quality_raw[key], key, 0, 1)
        for key in ("mean_conf", "visible_ratio", "lower_body_visible")
        if key in quality_raw
    }
    pose_quality = number(raw.get("pose_quality", quality.get("mean_conf", 0)), "pose_quality", 0, 1)
    branch_scores_raw = raw.get("branch_scores", {})
    if not isinstance(branch_scores_raw, dict):
        raise ValueError("branch_scores must be an object")
    branch_scores = {}
    for key in ("pose", "geometry"):
        if key in branch_scores_raw:
            branch_scores[key] = number(branch_scores_raw[key], f"branch_scores.{key}", 0, 1)
    timestamp = raw.get("timestamp", utc_now())
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise ValueError("timestamp must be an ISO 8601 string")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO 8601 string") from exc
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "received_at": utc_now(),
        "frame_seq": frame_seq,
        "edge_fps": edge_fps,
        "network_rtt_ms": network_rtt_ms,
        "fall_probability": probability,
        "pose_quality": pose_quality,
        "keypoints": clean_points,
        "quality": quality,
        "branch_scores": branch_scores,
        "model": model,
        "source": source,
    }


class State:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.devices: dict[str, dict] = {}
        self.subscribers: set[queue.Queue] = set()
        self.demo_stop = threading.Event()
        self.demo_thread: threading.Thread | None = None
        self.demo_scenario_running = False
        with closing(sqlite3.connect(DB_PATH)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                state TEXT NOT NULL, fall_probability REAL NOT NULL,
                pose_quality REAL NOT NULL, model TEXT NOT NULL,
                source TEXT NOT NULL, acknowledged_at TEXT, note TEXT
            )""")
            db.execute(SCHEMA)
            latest = db.execute("""SELECT payload, received_at FROM (
                SELECT payload, received_at,
                       ROW_NUMBER() OVER (PARTITION BY device_id
                           ORDER BY julianday(captured_at) DESC, received_at DESC) AS position
                FROM edge_records
            ) WHERE position=1""").fetchall()
            db.commit()
        # A cloud restart retains the last edge display as well as event history.
        # Freshness still derives from capture time, including an offline backlog.
        for payload, received_at in latest:
            item = json.loads(payload)
            reading = validate_reading({k:v for k,v in item.items() if k in READING_FIELDS}, source="edge_offline")
            epoch = datetime.fromisoformat(reading["timestamp"].replace("Z", "+00:00")).timestamp()
            self.devices[reading["device_id"]] = {
                **reading, "alert_state": item["alert_state"],
                "last_received_epoch": epoch, "received_at": received_at,
                "pose_backend": item.get("pose_backend", "unknown"),
            }

    def events(self, limit: int = 100) -> list[dict]:
        with closing(sqlite3.connect(DB_PATH)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    def snapshot(self, event_limit: int = 100) -> dict:
        with self.lock:
            devices = []
            now = time.time()
            for device in self.devices.values():
                public = {k: v for k, v in device.items() if k not in ("high_count", "low_count", "last_received_epoch")}
                public["online"] = now - device["last_received_epoch"] < 15
                devices.append(public)
            devices.sort(key=lambda item: item["received_at"], reverse=True)
        return {"server_time": utc_now(), "devices": devices, "events": self.events(event_limit), "demo_running": bool(self.demo_thread and self.demo_thread.is_alive())}

    def broadcast(self, payload: dict) -> None:
        with self.lock:
            for subscriber in tuple(self.subscribers):
                try:
                    subscriber.put_nowait(payload)
                except queue.Full:
                    try:
                        subscriber.get_nowait()
                        subscriber.put_nowait(payload)
                    except queue.Empty:
                        pass

    def ingest(self, reading: dict) -> dict:
        with self.lock:
            device_id = reading["device_id"]
            previous = self.devices.get(device_id, {})
            state = previous.get("alert_state", "normal")
            high_count = previous.get("high_count", 0)
            low_count = previous.get("low_count", 0)
            probability = reading["fall_probability"]
            event_state = None
            if probability >= 0.65:
                high_count += 1
                low_count = 0
                if state in ("normal", "cleared"):
                    state, event_state = "suspected", "suspected"
                if high_count >= 2 and probability >= 0.82 and state == "suspected":
                    state, event_state = "confirmed", "confirmed"
            elif probability <= 0.35:
                low_count += 1
                high_count = 0
                if state in ("suspected", "confirmed") and low_count >= 2:
                    state, event_state = "cleared", "cleared"
                elif state == "cleared":
                    state = "normal"
            else:
                high_count = 0
                low_count = 0
            reading = {**reading, "alert_state": state, "high_count": high_count, "low_count": low_count, "last_received_epoch": time.time()}
            self.devices[device_id] = reading
            if event_state:
                with closing(sqlite3.connect(DB_PATH)) as db:
                    db.execute("INSERT INTO events (device_id,timestamp,state,fall_probability,pose_quality,model,source) VALUES (?,?,?,?,?,?,?)", (device_id, reading["received_at"], event_state, probability, reading["pose_quality"], reading["model"], reading["source"]))
                    db.commit()
        self.broadcast({"type": "snapshot", "data": self.snapshot(10)})
        return {"device_id": device_id, "alert_state": state, "event_created": event_state}

    def acknowledge(self, event_id: int, note: str) -> dict | None:
        with self.lock:
            with closing(sqlite3.connect(DB_PATH)) as db:
                db.row_factory = sqlite3.Row
                row = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
                if not row:
                    return None
                if row["state"] != "confirmed":
                    raise ValueError("only confirmed events can be acknowledged")
                if row["acknowledged_at"] is None:
                    db.execute("UPDATE events SET acknowledged_at=?,note=? WHERE id=?", (utc_now(), note, event_id))
                    db.commit()
                result = dict(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())
        self.broadcast({"type": "snapshot", "data": self.snapshot(10)})
        return result

    def demo_reading(self, probability: float, seq: int, tilt: float = 0) -> dict:
        # Normalized COCO skeleton; no video frames or human identity are used.
        base = [(0.50,.13),(.48,.12),(.52,.12),(.46,.13),(.54,.13),(.42,.29),(.58,.29),(.36,.44),(.64,.44),(.34,.60),(.66,.60),(.45,.53),(.55,.53),(.43,.74),(.57,.74),(.42,.93),(.58,.93)]
        points = [[max(0,min(1,x + tilt*(y-.15))), y, round(.83 + random.random()*.12, 3)] for x,y in base]
        return validate_reading({"device_id": DEMO_DEVICE, "timestamp": utc_now(), "frame_seq": seq, "edge_fps": round(27 + random.random()*2, 1), "network_rtt_ms": round(28 + random.random()*8, 1), "fall_probability": probability, "pose_quality": .89, "keypoints": points, "model": "Synthetic demo / 合成演示"}, source="demo")

    def start_demo(self) -> bool:
        with self.lock:
            if self.demo_thread and self.demo_thread.is_alive():
                return False
            self.demo_stop.clear()
            def loop() -> None:
                seq = 1
                while not self.demo_stop.is_set():
                    if not self.demo_scenario_running:
                        self.ingest(self.demo_reading(round(.08 + random.random()*.11, 3), seq))
                        seq += 1
                    self.demo_stop.wait(1.5)
            self.demo_thread = threading.Thread(target=loop, daemon=True, name="synthetic-demo")
            self.demo_thread.start()
            return True

    def trigger_demo_fall(self) -> bool:
        with self.lock:
            if not self.demo_thread or not self.demo_thread.is_alive():
                return False
            if self.demo_scenario_running:
                return False
            self.demo_scenario_running = True
        def scenario() -> None:
            try:
                seq = int(time.time())
                for probability, tilt in ((.70,.12),(.91,.38),(.94,.48),(.90,.55),(.22,.08),(.16,0)):
                    if self.demo_stop.is_set():
                        break
                    self.ingest(self.demo_reading(probability, seq, tilt))
                    seq += 1
                    self.demo_stop.wait(1.2)
            finally:
                with self.lock:
                    self.demo_scenario_running = False
        threading.Thread(target=scenario, daemon=True, name="synthetic-fall").start()
        return True


STATE = State()
WORKSPACE = Workspace(DB_PATH, ROOT / "index.html", pi_camera_request)


class Handler(BaseHTTPRequestHandler):
    server_version = "FallGuard/1.0"

    def handle(self) -> None:
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, format: str, *args: object) -> None:
        if self.command == "GET" and urlparse(self.path).path in ("/", "/index.html", "/styles.css", "/app.js", "/favicon.svg", "/api/snapshot", "/api/stream", "/api/camera/pi/frame"):
            return
        print(f"{self.address_string()} - {format % args}", flush=True)

    def reply(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self, max_bytes: int = 64_000) -> object:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= max_bytes:
            raise ValueError(f"request body must be 1–{max_bytes} bytes")
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON") from exc

    def authorize_ingest(self) -> bool:
        if not INGEST_TOKEN:
            self.reply(503, {"error": "FALLGUARD_INGEST_TOKEN must be configured for live ingestion"})
            return False
        supplied = self.headers.get("X-Device-Token", "")
        if not hmac.compare_digest(supplied, INGEST_TOKEN):
            self.reply(401, {"error": "invalid device token"})
            return False
        return True

    def authorize_dashboard(self) -> bool:
        if not DASHBOARD_USER and not DASHBOARD_PASSWORD:
            return True
        header = self.headers.get("Authorization", "")
        try:
            scheme, token = header.split(" ", 1)
            credentials = base64.b64decode(token, validate=True).decode("utf-8")
            username, password = credentials.split(":", 1)
            valid = scheme.lower() == "basic" and hmac.compare_digest(username, DASHBOARD_USER) and hmac.compare_digest(password, DASHBOARD_PASSWORD)
        except (ValueError, UnicodeError, binascii.Error):
            valid = False
        if not valid:
            body = "Authentication required / 需要登录".encode("utf-8")
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="FallGuard dashboard"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        return valid

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self.reply(200, {"status": "ok", "service": "fallguard-dashboard", "storage": "ok", "time": utc_now(), "live_ingest_configured": bool(INGEST_TOKEN), "cloud_model": "edge_offline", "build": BUILD})
            return
        if not self.authorize_dashboard():
            return
        if WORKSPACE.get(self):
            return
        if path == "/api/camera/pi/frame":
            status, payload = pi_camera_frame()
            if status == 200:
                frame = payload
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(frame)
            elif status == 204:
                self.send_response(204)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            else:
                self.reply(status, payload)
            return
        if path == "/api/camera/pi/status":
            client_id = parse_qs(urlparse(self.path).query).get("client_id", [""])[0]
            status, payload = pi_camera_request("status", client_id)
            self.reply(status, payload)
            return
        if path == "/api/model/browser/info":
            self.reply(503, {"available": False, "error": CLOUD_MODEL_ERROR})
            return
        if path == "/api/snapshot":
            self.reply(200, STATE.snapshot())
            return
        if path == "/api/events":
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = max(1, min(200, int(query.get("limit", ["100"])[0])))
            except ValueError:
                self.reply(400, {"error": "invalid limit"})
                return
            self.reply(200, STATE.events(limit))
            return
        if path == "/api/stream":
            self.stream()
            return
        vendor_types = {
            "/vendor/mediapipe/vision_bundle.mjs": "text/javascript; charset=utf-8",
            "/vendor/mediapipe/pose_landmarker_lite.task": "application/octet-stream",
            "/vendor/mediapipe/wasm/vision_wasm_internal.js": "text/javascript; charset=utf-8",
            "/vendor/mediapipe/wasm/vision_wasm_internal.wasm": "application/wasm",
            "/vendor/mediapipe/wasm/vision_wasm_nosimd_internal.js": "text/javascript; charset=utf-8",
            "/vendor/mediapipe/wasm/vision_wasm_nosimd_internal.wasm": "application/wasm",
            "/vendor/mediapipe/wasm/vision_wasm_module_internal.js": "text/javascript; charset=utf-8",
            "/vendor/mediapipe/wasm/vision_wasm_module_internal.wasm": "application/wasm",
        }
        if path in vendor_types:
            file = ROOT / path.lstrip("/")
            compressed = file.with_name(file.name + ".gz")
            use_gzip = path.endswith(".wasm") and "gzip" in self.headers.get("Accept-Encoding", "") and compressed.is_file()
            if use_gzip:
                file = compressed
            self.send_response(200)
            self.send_header("Content-Type", vendor_types[path])
            self.send_header("Content-Length", str(file.stat().st_size))
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            if path.endswith(".wasm"):
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Cache-Control", "private, max-age=86400")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with file.open("rb") as source:
                while chunk := source.read(64 * 1024):
                    self.wfile.write(chunk)
            return
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if path not in files:
            self.reply(404, {"error": "not found"})
            return
        filename, content_type = files[path]
        body = (ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def stream(self) -> None:
        self.close_connection = True
        subscriber: queue.Queue = queue.Queue(maxsize=3)
        with STATE.lock:
            STATE.subscribers.add(subscriber)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            initial = {"type": "snapshot", "data": STATE.snapshot(10)}
            self.wfile.write(f"data: {json.dumps(initial, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    message = subscriber.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(message, ensure_ascii=False)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with STATE.lock:
                STATE.subscribers.discard(subscriber)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/edge/records":
                if not self.authorize_ingest():
                    return
                result = import_records(STATE, DB_PATH, self.read_json(256_000), validate_reading, utc_now)
                self.reply(200, result)
                return
            if path == "/api/pose":
                if not self.authorize_ingest():
                    return
                self.reply(503, {"error": CLOUD_MODEL_ERROR})
                return
            if path == "/api/ingest":
                if not self.authorize_ingest():
                    return
                self.reply(202, STATE.ingest(validate_reading(self.read_json())))
                return
            if not self.authorize_dashboard():
                return
            if WORKSPACE.post(self):
                return
            if path in ("/api/camera/pi/start", "/api/camera/pi/stop"):
                raw = self.read_json()
                if not isinstance(raw, dict) or set(raw) != {"client_id"} or not isinstance(raw.get("client_id"), str):
                    raise ValueError("client_id is required")
                status, payload = pi_camera_request(path.rsplit("/", 1)[1], raw["client_id"])
                self.reply(status, payload)
                return
            if path in ("/api/model/browser/frame", "/api/model/browser/reset", "/api/model/select"):
                self.reply(503, {"error": CLOUD_MODEL_ERROR})
                return
            if path == "/api/demo/start":
                self.reply(200, {"started": STATE.start_demo()})
                return
            if path == "/api/demo/fall":
                if not STATE.trigger_demo_fall():
                    self.reply(409, {"error": "start demo stream first"})
                else:
                    self.reply(200, {"triggered": True})
                return
            if path == "/api/demo/stop":
                STATE.demo_stop.set()
                self.reply(200, {"stopped": True})
                return
            match = re.fullmatch(r"/api/events/(\d+)/ack", path)
            if match:
                raw = self.read_json()
                if not isinstance(raw, dict):
                    raise ValueError("JSON object required")
                note = raw.get("note", "")
                if not isinstance(note, str) or len(note) > 200:
                    raise ValueError("note must be at most 200 characters")
                event = STATE.acknowledge(int(match.group(1)), note.strip())
                self.reply(200, event) if event else self.reply(404, {"error": "event not found"})
                return
            self.reply(404, {"error": "not found"})
        except ValueError as exc:
            self.reply(400, {"error": str(exc)})


def main() -> None:
    if bool(DASHBOARD_USER) != bool(DASHBOARD_PASSWORD):
        raise SystemExit("Set both FALLGUARD_DASHBOARD_USER and FALLGUARD_DASHBOARD_PASSWORD")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"FallGuard listening on http://{HOST}:{PORT}; database={DB_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STATE.demo_stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
