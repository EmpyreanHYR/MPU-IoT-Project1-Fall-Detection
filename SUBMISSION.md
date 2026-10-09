# Final submission — 9 October 2026

Course: COMP6131 Internet of Things Essentials, Group 7.

The course guideline (Required Project Documents and Evidence, item 7) accepts a
**repository link or code archive**, together with an environment file, run
instructions and configuration for the main demonstration.

## Submission files

- [Final report PDF](docs/downloads/fallguard-final-report.pdf) and [LaTeX source](manuscripts/final-report/fall_detection_final_report.tex).
- [Appendix A: individual work and reflection](docs/downloads/fallguard-personal-contributions.pdf) and its independent [IEEE two-column LaTeX source](manuscripts/final-report/personal_contributions.tex).
- [Presentation PDF](docs/downloads/fallguard-presentation.pdf) and the [interactive deck](docs/index.html), with [English](docs/speaker-notes.md) and [Chinese](docs/speaker-notes-zh.md) speaker notes.
- Reproducibility: this repository, [environment and run guide](deployment/README.md), [selected model](artifacts/models/README.md), [experiment code](code/README.md), [results](results/README.md) and [experiment rebuild guide](REPRODUCIBILITY.md).

Meeting minutes are provided in the course submission package. The similarity
report is added separately by the submitting student.

## Fixed repository version

Use tag **`submission-2026-10-09-v4`** for this handover. The course package records
its full commit ID and includes a source ZIP. The tag identifies the submitted
materials; the commit ID is the permanent reference for the file contents.

```sh
git clone --branch submission-2026-10-09-v4 --depth 1 https://github.com/EmpyreanHYR/MPU-IoT-Project1-Fall-Detection.git
cd MPU-IoT-Project1-Fall-Detection
```

## Run and verify

Create a Python 3.12 environment and install the deployment requirements:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r deployment/requirements.txt
python scripts/verify_assets.py
python scripts/build_release_manifest.py --check
python scripts/run_deployment.py --mode local
```

The last command starts the local edge dashboard, record API, cloud backend and
synchronization worker. It prints their loopback URLs. Camera inference is
started by adding a local source and separately obtained pose model as described
in [deployment/README.md](deployment/README.md). The selected temporal model is
included. Two-host cloud deployment, configuration templates and service units
are in the same guide; set your own tokens and host addresses.

To run the software verification used in CI:

```sh
python -m pip install 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r deployment/requirements-test.txt
python -m unittest discover -s tests -v
node tests/check_dashboard_ui.cjs
node tests/check_dashboard_ui.cjs ../webui/index.html
```

The CPU-index command follows the Linux CI environment; on macOS, install
PyTorch from the default PyPI index instead.

The [submission verification record](submission/verification-2026-10-09.json)
contains the local checks and environment scope.

The tests cover real local HTTP delivery, durable records, restart recovery,
model interfaces and grouped-fold isolation. The dated hardware/cloud results
are in [results/edge](results/edge) and [results/deployment](results/deployment).

## Build the report and appendix

```sh
cd manuscripts/final-report
make
```

This creates **two independent PDFs**, one for the report and one for Appendix A.
Submit Appendix A alongside the report. The main report fits the course's
10-page A4 limit. No production credentials or source videos are needed to read
the materials or verify the included model hashes.
