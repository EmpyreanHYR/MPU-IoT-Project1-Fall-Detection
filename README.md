# FallGuard — MPU IoT Project 1

Camera-based fall detection with quality-aware temporal modeling, independent Raspberry Pi inference, and deferred cloud record delivery.

**[Open the English project presentation](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/)**

The presentation includes 12 paged slides, approximately seven minutes of prepared English speaker notes, a [Chinese speaker guide](docs/speaker-notes-zh.html), a [two-screen presenter console](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/presenter.html) with a timer and synchronized controls, evidence and Q&A appendices, mouse-line highlighting, interactive model/ablation/robustness charts, and a searchable archive of 1,853 aggregate rows with excluded spatial-mask conditions clearly labeled. It also includes the Raspberry Pi and cloud recovery evidence. Download or clone the repository and open [`docs/index.html`](docs/index.html) to use it locally without a CDN or backend.

## Repository layout

| Directory | Purpose |
| --- | --- |
| [`docs/`](docs/) | English HTML presentation, figures, speaker notes and bundled data; GitHub Pages publishes this directory. |
| [`scripts/`](scripts/) | Standard-library builder for the presentation data. |
| [`code/`](code/) | Model code, experiment configurations and evaluation instructions. |
| [`manuscripts/`](manuscripts/) | LaTeX sources for the proposal and final report. |
| [`results/`](results/) | Aggregate model CSV evidence and a public, compact edge/system summary. |
| [`datasets/`](datasets/) | Dataset provenance and usage documentation; no raw videos. |
| [`webui/`](webui/) | Original dashboard frontend and browser-side MediaPipe assets. |

## Main findings

- MaskedBiMamba has primary window precision 0.6048 and video F1 0.7632; the Transformer encoder leads clean window F1 at 0.6581.
- Under 30% frame removal, primary window F1 is 0.6276 for MaskedBiMamba and 0.4361 for TCNTE.
- With the same YOLOv8s-pose comparison, Raspberry Pi + Hailo runs the complete local pipeline at 20.56 fps versus 1.73 fps for CPU ONNX.
- The 40-clip synthetic test has 20 true positives, 11 true negatives, 8 false positives and 1 missing output. These clip-level results do not establish continuous-monitoring reliability.
- Fixed-rule replay gives confirmed-event recall 0.7752 and 66.7 unmatched confirmed alerts per evaluated video hour. These are segmented-test rates, not continuous-care notification rates.
- The cloud delivery tests match all 85 edge records. Following a 30-second upload-path outage, the queue of 17 records is first observed empty 2.83 seconds after recovery.

See the presentation and manuscript for protocols, sample variation and limitations. This is a research prototype, not a clinically validated alarm system.

## Local presentation

```sh
python3 scripts/build_presentation_data.py
python3 -m http.server 8080
```

Open `http://localhost:8080/docs/`, or open `docs/index.html` directly. See [`docs/README.md`](docs/README.md) for keyboard controls and Pages configuration.

The final manuscript source is synchronized with the current report, including an independent repository block after the keywords, a single shared IEEE affiliation, fixed-rule alert replay, and valid robustness conditions. PNG figures are included; compiled PDFs and LaTeX build outputs remain excluded from Git. Build using the manuscript's Makefile. The included [`personal_contributions.tex`](manuscripts/final-report/personal_contributions.tex) is inserted after the bibliography in the same PDF and records Yaorong Huang's reported work in code, writing and the presentation; the other four members retain name-and-TBD entries for their own completion.

Production deployment files, credentials, raw camera footage, databases and private device addresses are not part of this repository. GitHub Pages serves the static presentation; it does not host the live detection or cloud services.

## Evidence status

Current robustness plots use frame removal and confidence noise. Archived joint-removal and lower-body-removal conditions are excluded because zero filling before normalization rescaled other joints. Original values remain in the annotated CSV and a separate excluded-history view. The corrected preprocessing is included in `code/src/fallbench/data.py`; the excluded experiments have not been rerun.
