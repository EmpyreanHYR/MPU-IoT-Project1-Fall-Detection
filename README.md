# FallGuard — MPU IoT Project 1

Camera-based fall detection with quality-aware temporal modeling, independent Raspberry Pi inference, and deferred cloud record delivery.

**[Open the English project presentation](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/)**

**[Final submission files and fixed version](SUBMISSION.md)** · **[Report, contribution appendix and presentation PDFs](docs/downloads/)** ·
[Chinese source guides](documentation/zh/)

The presentation includes 12 paged slides, approximately seven minutes of prepared English speaker notes, a [Chinese speaker guide](docs/speaker-notes-zh.html), a [two-screen presenter console](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/presenter.html) with a timer and synchronized controls, evidence and Q&A appendices, mouse-line highlighting, interactive model/ablation/robustness charts, and a searchable archive of 1,853 aggregate rows with excluded spatial-mask conditions clearly labeled. It also includes the Raspberry Pi and cloud recovery evidence. Download or clone the repository and open [`docs/index.html`](docs/index.html) to use it locally without a CDN or backend.

## Repository layout

| Directory | Purpose |
| --- | --- |
| [`docs/`](docs/) | English HTML presentation, figures, speaker notes and bundled data; GitHub Pages publishes this directory. |
| [`scripts/`](scripts/) | Presentation builders, unified service launcher, pose-model preparation and asset verification. |
| [`deployment/`](deployment/) | Offline edge inference, durable outbox, cloud sync, local dashboard and generic service/configuration templates. |
| [`artifacts/models/`](artifacts/models/) | Selected temporal classifier weights, ONNX, model card and checksums. |
| [`code/`](code/) | Model code, experiment configurations and evaluation instructions. |
| [`manuscripts/`](manuscripts/) | LaTeX sources for the proposal and final report. |
| [`documentation/zh/`](documentation/zh/) | Updated Chinese mathematical, workflow and project guides. |
| [`results/`](results/) | Aggregate model CSV evidence and a public, compact edge/system summary. |
| [`datasets/`](datasets/) | Dataset provenance and usage documentation; no raw videos. |
| [`webui/`](webui/) | Dashboard frontend, cloud record receiver and browser-side MediaPipe assets. |

## Main findings

- MaskedBiMamba has primary window precision 0.6048 and video F1 0.7632; the Transformer encoder leads clean window F1 at 0.6581.
- Under 30% frame removal, primary window F1 is 0.6276 for MaskedBiMamba and 0.4361 for TCNTE.
- With the same YOLOv8s-pose comparison, Raspberry Pi + Hailo runs the complete local pipeline at 20.56 fps versus 1.73 fps for CPU ONNX.
- The 40-clip synthetic test has 20 true positives, 11 true negatives, 8 false positives and 1 missing output. These clip-level results do not establish continuous-monitoring reliability.
- Fixed-rule replay gives confirmed-event recall 0.7752 and 66.7 unmatched confirmed alerts per evaluated video hour. These are segmented-test rates, not continuous-care notification rates.
- The cloud delivery tests match all 85 edge records. Following a 30-second upload-path outage, the queue of 17 records is first observed empty 2.83 seconds after recovery.

The manuscript gives the shared evaluation protocols and a concise section on the next improvements: alert calibration, cross-dataset specificity and longer camera trials.

## Local presentation

```sh
python3 scripts/build_presentation_data.py
python3 -m http.server 8080
```

Open `http://localhost:8080/docs/`, or open `docs/index.html` directly. See [`docs/README.md`](docs/README.md) for keyboard controls and Pages configuration.

The report and Appendix A are independent A4 IEEE two-column documents. The
main report and references fit the ten-page course limit. Appendix A consolidates
all five members' work, problems, solutions and reflection from the supplied
team records. The manuscript Makefile also builds Yaorong Huang's individual copy. The [submission
entry](SUBMISSION.md) links the PDFs, environment, run instructions and fixed
repository tag. A twelve-slide PDF accompanies the interactive presentation. Yaorong Huang’s expanded contribution also has an independent two-page IEEE reading/submission copy.

Sanitized deployment source and generic templates are included. Production credentials, raw camera footage, databases and private device addresses remain excluded. GitHub Pages serves the static presentation; it does not host the live detection or cloud services.

## Current operational workspaces — 7 October 2026

The Pi workspace `2026.10.07` and cloud workspace `2026.10.07-cloud` include live preview, fresh-result states, historical probability charts, filtered/paginated records, CSV export and device diagnostics. Local inference and storage work without the cloud. The cloud keeps its own archive and reads current Pi status through a token-protected private bridge; expired or invalid results clear the current probability. Camera controls validate same-origin JSON and a page token.

The production update retained 3,304 classified windows and 306 event rows, with zero pending records at the check. These are operational counts, not accuracy samples. The [dated deployment verification](results/deployment/) separates actual service checks from synthetic integration fixtures and the earlier hardware experiments. Your own installation uses the [deployment guide](deployment/README.md).

## Evidence status

Current robustness plots use frame removal and confidence noise. Archived joint-removal and lower-body-removal conditions are excluded because zero filling before normalization rescaled other joints. Original values remain in the annotated CSV and a separate excluded-history view. The corrected preprocessing is included in `code/src/fallbench/data.py`; the excluded experiments have not been rerun.

## Run the system and reproduce the work

See [deployment instructions](deployment/README.md) for the one-command local launcher, camera/CPU/Hailo modes, cloud synchronization and Linux service templates. The selected [temporal model](artifacts/models/README.md) is included; separately licensed pose weights can be obtained and exported with `scripts/prepare_pose_model.py`.

[Reproducibility status and full rebuild commands](REPRODUCIBILITY.md) distinguish the recovered 260-video test assignment from newly generated validation folds. Original validation assignments and pose caches are not available in this release. CI verifies the model interface, numerical parity and delivery behavior on every push.

Browser-camera demonstration is restored alongside the edge workspace at `/browser-demo.html#live`, including current-model inference, available server reference models, synthetic scenarios and event history.
