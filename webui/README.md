# FallGuard dashboard frontend

This directory contains only the dashboard's browser-facing files:

- `index.html` — interface structure;
- `styles.css` — visual styling;
- `app.js` — browser interaction and API integration logic;
- `favicon.svg` — project icon;
- `vendor/mediapipe/` — locally served MediaPipe browser assets and their license.

No backend source, deployment configuration, credentials, runtime database, device address, private-network information, or machine-specific path is included.

The frontend uses relative `/api/...` paths. A separately managed backend must provide those endpoints when the complete system is run. Opening the files without that backend is suitable only for inspecting the interface source; live status, event history, camera control, and model inference require the private backend.

## Privacy guidance

Do not commit `.env` files, passwords, tokens, certificates, device addresses, private server addresses, databases, camera recordings, personal images, pose records, or deployment service files. The repository-level `.gitignore` blocks common sensitive and deployment-specific paths as an additional safeguard.

