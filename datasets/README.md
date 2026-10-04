# Dataset documentation

This directory records dataset sources, versions, licenses, processing boundaries, and actual project usage. It intentionally contains no videos, extracted frames, pose caches, subject-level raw records, or downloaded archives.

- `DATASET_INVENTORY_AND_USAGE_PLAN.md` is the original pre-experiment inventory and usage plan.
- `DATASET_PROVENANCE_AND_USAGE.md` records the verified versions and experiment roles using anonymized workspace paths.

Obtain each dataset from its cited publisher and comply with its own license. The repository does not grant redistribution rights for third-party data.


`primary_test_folds.csv` recovers the 260 primary video test assignments from saved predictions, checked across all 60 main runs. Its provenance file records source hashes. It does not reconstruct the original training/validation assignments. See [rebuild instructions](../REPRODUCIBILITY.md) for that distinction.
