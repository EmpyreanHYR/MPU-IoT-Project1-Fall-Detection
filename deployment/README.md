# Run the offline edge and cloud system

The public code includes the actual offline inference pipeline, SQLite outbox,
edge dashboard, cloud workspace/record receiver and commit-before-ack puller.
Machine-specific configurations are replaced by templates. GitHub Pages hosts
the presentation; the services below run on your computer or devices.

## One-command local services

From the repository root, with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r deployment/requirements.txt
.venv/bin/python scripts/verify_assets.py
.venv/bin/python scripts/run_deployment.py
```

Open the cloud dashboard at `http://127.0.0.1:18080` and the local edge dashboard
at `http://127.0.0.1:18300`. This starts the receiver, persistent outbox, puller
and dashboards. The camera remains stopped until a source is supplied; no sample
fall probability is generated. Ctrl-C stops all child processes together.
SQLite records remain in the ignored `data/local-deployment/` directory.

## Enable camera or video inference

The temporal fall classifier is included in [`artifacts/models/`](../artifacts/models/).
The separately licensed YOLO pose model must be obtained from its publisher.
The helper downloads **YOLOv8s-pose** from a versioned official release and exports
the fixed 640-pixel, no-NMS ONNX interface expected by `CpuPose`:

```sh
.venv/bin/python -m pip install 'ultralytics>=8.3,<9' 'onnx>=1.17,<2'
.venv/bin/python scripts/prepare_pose_model.py --output-dir data/models
.venv/bin/python scripts/run_deployment.py \
  --source 0 --backend cpu --cpu-model data/models/yolov8s-pose.onnx
```

Replace `0` with a local video path for file input. FFmpeg and FFprobe must be
installed for video files; cameras use OpenCV. A file's source timestamps build
the one-second windows. The runtime stops at end of file and the launcher stops
the other services. Use the Pi for sustained real-time inference; local CPU
speed is hardware-dependent.

On a Raspberry Pi 5 + Hailo device, install its matching HailoRT Python runtime
and the compatible **YOLOv8s-pose Hailo-10H HEF** first. Then use:

```sh
.venv/bin/python scripts/run_deployment.py --mode edge \
  --source 0 --backend auto \
  --hef /usr/share/hailo-models/yolov8s_pose_h10.hef \
  --cpu-model data/models/yolov8s-pose.onnx
```

Set `FALLGUARD_INGEST_TOKEN` before edge-only or cloud-only mode. `auto` falls back
to local CPU if Hailo initialization/inference fails; both weights must exist.
`hailo` requires the accelerator and does not fall back. An arbitrary pose HEF
is not interchangeable: the decoder expects the three stride outputs and
17-keypoint layout implemented in `pose_backend.py`.
The recorded 20.56/1.73 fps comparison used the same YOLOv8s pose model; it is
historical evidence, not a speed guarantee for this checkout.

## Separate hosts and persistent Linux services

The edge keeps inference and UUID-addressed records without the cloud. The cloud
pulls batches of at most 100, durably commits them, then acknowledges precisely
those UUIDs. A lost acknowledgement causes a safe retry. Capture time is retained
and controls freshness, so an old backlog is not displayed as a new live event.

Templates assume the checkout is `/opt/fallguard`, its environment is
`/opt/fallguard/.venv`, and a dedicated `fallguard` user/group exists. Install
runtime dependencies there. Copy the two configuration examples to
`/etc/fallguard/edge.env` and `/etc/fallguard/cloud.env` as appropriate, replace
their token/password placeholders, and make them readable only by root and the
service group. Generate values with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.
The edge token must match `FALLGUARD_EDGE_RECORDS_TOKEN` on the cloud; the cloud
ingestion token is independent. Place the CPU pose weights at the configured
path and ensure the service user can access the camera/Hailo devices through
the device permissions of your OS installation.

For two hosts, set `FALLGUARD_RELAY_HOST` to the edge's private/VPN address and
`FALLGUARD_EDGE_RECORDS_URL` to that reachable address on port 18082. Keep the
record API on that private transport. The cloud receiver remains on loopback;
serve its dashboard through your HTTPS reverse proxy or an SSH tunnel.

Copy the applicable [`systemd/*.service`](systemd/) templates to
`/etc/systemd/system/`, then run:

```sh
sudo systemctl daemon-reload
# On the edge:
sudo systemctl enable --now fallguard-edge-outbox fallguard-edge-inference fallguard-edge-dashboard
# On the cloud:
sudo systemctl enable --now fallguard-cloud fallguard-cloud-sync
```

The outbox is independent of the inference process and keeps the backlog
available while the camera is stopped. Inference uses `--no-api` to avoid a
second listener. Systemd creates `/var/lib/fallguard-edge`,
`/var/lib/fallguard-cloud` and `/run/fallguard-edge` with the service ownership.
Check status with `systemctl status` and `journalctl -u SERVICE_NAME`.

The cloud workspace runs **edge-classified record ingestion**. Its preview and
diagnostics read the private outbox's token-protected `/dashboard/status` and
`/dashboard/preview`, which proxy the local edge dashboard. The cloud service
must load the same record URL/token as the puller. The outbox's default local
dashboard URL is `http://127.0.0.1:18300`; use `--dashboard-url` for another port.
The cloud archive stays available while the edge is disconnected, and current
probability is cleared for expired or incomplete poses. Historical
browser-camera inference and model selection are restored at `/browser-demo.html#live`. Remote camera controls remain
disabled in the templates; existing private relay installations can set
`FALLGUARD_PI_RELAY_URL` and the exact HTTPS `FALLGUARD_PUBLIC_ORIGIN`.

## Verify the deployment

```sh
.venv/bin/python -m pip install -r deployment/requirements-test.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python code/scripts/export_mamba_onnx.py \
  artifacts/models/masked_bimamba.pt data/models/reexport.onnx --quality-input
```

On Linux, install CPU PyTorch first with
`python -m pip install 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu`
to avoid downloading GPU packages for these checks. The CI runs the same tests
and export on every push. Tests use temporary databases, loopback HTTP services
and explicitly synthetic software fixtures. They verify delivery and numerical
interfaces; they do not produce new accuracy or clinical validation results.

Upstream interfaces: [Ultralytics pose/export documentation](https://docs.ultralytics.com/tasks/pose/),
[official YOLOv8 assets](https://github.com/ultralytics/assets/releases/tag/v8.3.0),
and [Hailo pose example](https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main/runtime/python/pose_estimation).

## Local dashboard workspace

The edge dashboard includes live preview, fresh-prediction states, a historical
120-window probability chart, filtered/paginated records, CSV export (latest
10,000 matching records), and local temperature/memory/disk/load diagnostics.
It keeps all assets on the device. Pending counts and acknowledgement timestamps
are delivery evidence, not a live network probe. Lost connections, expired
predictions and insufficient pose quality clear the current probability.

On the existing Pi user-service installation, optionally pass
`--camera-service fallguard-camera.service` to the dashboard to enable local
start/pause buttons. Control uses an exact localhost Host/Origin check and a
per-process token; generic system-service deployments keep control disabled.
Pausing inference preserves the database and leaves the independent outbox
running. JPEG previews use a cached display-size image when OpenCV is available;
JSON/CSV responses support gzip. To verify these changes:

```sh
python3 -m unittest discover -s tests -p test_dashboard.py -v
node tests/check_dashboard_ui.cjs
```

The cloud workspace uses the same three-page layout, with cloud SQLite history,
received timestamps, CSV export, and current edge telemetry. Verify its backend
and actual UI script with:

```sh
python3 -m unittest discover -s tests -p test_cloud_workspace.py -v
node tests/check_dashboard_ui.cjs ../webui/index.html
```

`deployment/cloud/update_cloud_workspace.py` is the updater for the existing
Tencent VM installation at `/root/跌倒检测/webui`. It expects a sibling verified
`manifest.json` and packaged source files, backs up source/systemd overrides and
SQLite, restarts the existing services, and rolls source/configuration back on
failure while retaining the live database. It is not the generic installer.

## Release consistency

`release-manifest.json` identifies the edge/cloud source, selected weights, manuscript source, Chinese guides and reviewed PDFs in this release. After updating them, run `python3 scripts/build_release_manifest.py`; verify with `--check`. CI checks this manifest and both actual page scripts in addition to the existing model/delivery tests. Production installations can save the published Git revision alongside their private configuration; credentials remain outside Git.

## Browser demonstration restored (7 October)

Open “本机在线演示” in the cloud sidebar. Camera landmarks are extracted by the bundled MediaPipe assets; the current two-input MaskedBiMamba runs on the server. This camera demonstration uses MediaPipe visibility as the quality box proxy, so it is a separate path from the evaluated YOLO edge pipeline. Existing server-side reference models remain selectable when their weights/runtime are installed. Synthetic Demo Studio and alert history are available in the restored page. The edge workspace and offline services remain in place.
