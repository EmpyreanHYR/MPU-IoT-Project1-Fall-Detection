# Workspace deployment verification — 7 October 2026

The edge workspace is `2026.10.07`; the cloud workspace is
`2026.10.07-cloud`. Both provide detection overview, historical records and
device diagnostics. The Pi performs pose extraction and temporal classification
independently of the cloud. The cloud receives already-classified records and
queries its durable archive; a protected private bridge provides current Pi
status and annotated preview.

Actual production checks confirmed three active edge services and three active
cloud services. The cloud update retained 3,304 classified-window rows and 306
event rows; the edge queue was empty at the check. These counts are a dated
operational snapshot, not evaluation sample counts or independent falls.
The private bridge rejects missing device tokens. Public dashboard/status/preview
requests require the existing login, and the public device-write route remains
unavailable. Source/configuration/database backups were created before updates.

Software validation uses explicitly synthetic temporary fixtures: five cloud
workspace tests, nine local dashboard tests, six offline/synchronization tests,
and one real-process launcher/delivery/bridge/shutdown test. The actual local and
cloud JavaScript scripts were checked for invalid poses, stale predictions,
paused services and connection loss. The cloud additionally preserves history
and shows an unknown pending count when the Pi is unreachable.

The September hardware and model measurements remain in
[`../edge/`](../edge/) and the corresponding experiment results. The October
checks do not constitute new accuracy, all-day reliability or clinical evidence.
Production tokens, database payloads and private device addresses are omitted
from this public summary.

See [`workspace-validation.json`](workspace-validation.json) and the
[`deployment guide`](../../deployment/README.md).
