# FallGuard cloud dashboard

The browser UI is served by `server.py`. `edge_ingest.py` imports offline edge records transactionally, preserves UUIDs and capture times, and creates each transition at most once. SQLite data, tokens and machine-specific configurations remain excluded.

Use the [deployment guide](../deployment/README.md) and unified launcher. The cloud workspace provides live edge preview/status, a 120-window archive chart, filtered and paginated records, CSV export, and edge diagnostics. `cloud_workspace.py` reads the private, device-token-protected outbox bridge using `FALLGUARD_EDGE_RECORDS_URL` and `FALLGUARD_EDGE_RECORDS_TOKEN`. The device token stays on the backend. If the edge is unreachable, the current result is cleared and cloud history remains available.

The backend receives classifications computed on the edge. Historical browser/cloud-model inference is unavailable. Remote camera buttons are enabled only with a separately configured private Pi relay; HTTPS deployments must set `FALLGUARD_PUBLIC_ORIGIN` to the exact browser origin. Controls require an authenticated dashboard, same-origin JSON, and a per-process control token. GitHub Pages publishes the report presentation under `docs/`, not this runtime service.

`vendor/mediapipe/` retains its bundled browser assets and upstream license. All backend routes use relative `/api/...` paths. An opened static HTML file cannot connect to a live SQLite/backend automatically.
