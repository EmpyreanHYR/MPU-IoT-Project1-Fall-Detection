# Data contract

## Segment manifest

Required CSV columns:

| Column | Type | Meaning |
|---|---|---|
| `video_id` | string | Stable ID unique across datasets |
| `path` | string | Video path, absolute or relative to a declared root |
| `dataset` | string | Dataset source |
| `subject` | string | Subject/group ID; use `unknown` only when unavailable |
| `view` | string | Camera/view ID, may be empty |
| `label` | string | `fall`, `fallen`, an ADL name, or `ignore` |
| `start` | float | Segment start in seconds; empty means video start |
| `end` | float | Segment end in seconds; empty means video end |

Intervals are half-open: `[start, end)`. Overlapping contradictory labels are
an audit error. Mapping `fallen` or `lying` to the positive class requires a
separate named protocol.

## Pose cache

One compressed NPZ file is produced for every video:

```text
timestamps      float64 [frames]
keypoints       float32 [frames, 17, 3]  # normalized x, y, confidence
bbox            float32 [frames, 5]      # normalized cx, cy, w, h, confidence
track_id        int64   [frames]          # -1 when absent
video_id        scalar string
dataset         scalar string
subject         scalar string
source_path     scalar string
pose_model      scalar string
```

`index.csv` maps `video_id` to its cache file and records extraction status.
Raw RGB is not copied into the cache.

## Fold manifest

This is the segment manifest plus:

```text
fold,split
```

`split` is one of `train`, `val`, or `test`. All rows belonging to one subject
or grouping unit must have the same split within a fold.

## Window manifest

One row is one classifier sample:

```text
window_id,cache_path,video_id,dataset,subject,view,split,start,end,label
```

Windows are generated only after the fold assignment. Overlapping windows from
one video therefore cannot cross splits.

