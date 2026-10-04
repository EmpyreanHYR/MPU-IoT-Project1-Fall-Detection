# FallGuard cloud dashboard

The browser UI is served by `server.py`. `edge_ingest.py` imports offline edge records transactionally, preserves UUIDs and capture times, and creates each transition at most once. SQLite data, tokens and machine-specific configurations remain excluded.

Use the [deployment guide](../deployment/README.md) and unified launcher. The public backend receives classifications computed on the edge; historical browser/cloud-model inference and private remote-camera control are unavailable without their separate components. The edge camera preview uses the included local dashboard. GitHub Pages publishes the report presentation under `docs/`, not this runtime service.

`vendor/mediapipe/` retains its bundled browser assets and upstream license. All backend routes use relative `/api/...` paths. An opened static HTML file cannot connect to a live SQLite/backend automatically.
