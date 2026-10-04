# Local video mapping templates

These three CSV templates list the exact annotation paths from the recorded
OmniFall revision, with blank `video_path` cells for you to fill with authorized
local video files. They contain 100 CAUCAFall, 160 GMDCSA-24 and 190 Le2i identities.
They do not contain source videos or personal/local filesystem paths.

Copy the applicable file into your work directory, fill every `video_path`,
then supply it to `prepare_omnifall_manifest.py --path-mapping`.
Missing entries are rejected; do not infer labels from a similar filename.
The pinned source URLs, segment counts and SHA-256 hashes are recorded in
[`annotation_sources.json`](../annotation_sources.json).

The primary training pipeline takes only `caucafall.csv` and `GMDCSA24.csv`.
`le2i.csv` belongs to the external/reproduction track. See
[the complete reconstruction guide](../../REPRODUCIBILITY.md).
