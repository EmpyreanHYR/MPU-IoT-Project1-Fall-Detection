#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import av
from ultralytics import YOLO
from tqdm import tqdm


def resolve_source(path: str, root: Path | None) -> Path:
    source = Path(path)
    if not source.is_absolute() and root is not None:
        source = root / source
    return source.resolve()


def video_probe(source: Path) -> tuple[float, bool]:
    """Return FPS and whether OpenCV can decode the first frame."""
    capture = cv2.VideoCapture(str(source))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    decodes, _ = capture.read()
    capture.release()
    if not np.isfinite(fps) or fps <= 0:
        with av.open(str(source)) as container:
            stream = container.streams.video[0]
            rate = stream.average_rate or stream.guessed_rate
            fps = float(rate) if rate is not None else 0.0
    return fps, bool(decodes)


def av_frames(source: Path):
    """Decode AV1 and other codecs absent from the OpenCV wheel in software."""
    with av.open(str(source)) as container:
        for frame in container.decode(video=0):
            yield frame.to_ndarray(format="bgr24")


def tracking_results(model: YOLO, source: Path, opencv_decodes: bool, args):
    common = dict(tracker=args.tracker, classes=[0], conf=args.confidence,
                  device=args.device, verbose=False)
    if opencv_decodes:
        # Let Ultralytics reset its tracker when the input path changes while
        # retaining state across frames of the same video stream.
        yield from model.track(source=str(source), stream=True, persist=False, **common)
        return

    # Ultralytics relies on OpenCV for path inputs. Feed PyAV-decoded frames
    # individually so AV1 OmniFall videos remain usable without transcoding.
    if getattr(model, "predictor", None) is not None:
        for tracker in getattr(model.predictor, "trackers", []):
            tracker.reset()
    for frame in av_frames(source):
        batch = model.track(source=frame, stream=False, persist=True, **common)
        if batch:
            yield batch[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract COCO-17 pose tracks once per video.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--video-root", type=Path)
    parser.add_argument("--model", default="yolov8s-pose.pt")
    parser.add_argument("--tracker", default="botsort.yaml")
    parser.add_argument("--device", default="0")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    table = pd.read_csv(args.manifest, dtype={"video_id": str, "subject": str})
    videos = table.drop_duplicates("video_id")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.model)
    index_rows: list[dict[str, object]] = []
    for row in tqdm(list(videos.itertuples()), desc="videos"):
        source = resolve_source(str(row.path), args.video_root)
        if not source.exists():
            raise FileNotFoundError(source)
        cache_name = hashlib.sha1(f"{row.dataset}|{source}".encode()).hexdigest()[:20] + ".npz"
        destination = (args.output_dir / cache_name).resolve()
        if destination.exists() and not args.overwrite:
            index_rows.append({"video_id": row.video_id, "cache_path": str(destination),
                               "source_path": str(source), "status": "existing"})
            continue
        fps, opencv_decodes = video_probe(source)
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"Invalid FPS for {source}: {fps}")
        timestamps: list[float] = []
        keypoints: list[np.ndarray] = []
        boxes: list[np.ndarray] = []
        track_ids: list[int] = []
        selected_track: int | None = None
        results = tracking_results(model, source, opencv_decodes, args)
        for frame_index, result in enumerate(results):
            timestamps.append(frame_index / fps)
            frame_keypoints = np.zeros((17, 3), dtype=np.float32)
            frame_box = np.zeros(5, dtype=np.float32)
            frame_track = -1
            if result.boxes is not None and len(result.boxes) and result.keypoints is not None:
                xywh = result.boxes.xywhn.detach().cpu().numpy()
                confidence = result.boxes.conf.detach().cpu().numpy()
                identities = (result.boxes.id.detach().cpu().numpy().astype(int)
                              if result.boxes.id is not None else np.full(len(xywh), -1))
                candidates = np.arange(len(xywh))
                if selected_track is not None and selected_track in identities:
                    selected = int(np.where(identities == selected_track)[0][0])
                else:
                    selected = int(candidates[np.argmax(xywh[:, 2] * xywh[:, 3])])
                    if identities[selected] >= 0:
                        selected_track = int(identities[selected])
                points = result.keypoints.xyn[selected].detach().cpu().numpy()
                point_conf = result.keypoints.conf[selected].detach().cpu().numpy()
                frame_keypoints[:, :2] = points
                frame_keypoints[:, 2] = point_conf
                frame_box[:4] = xywh[selected]
                frame_box[4] = confidence[selected]
                frame_track = int(identities[selected])
            keypoints.append(frame_keypoints)
            boxes.append(frame_box)
            track_ids.append(frame_track)
        if not timestamps:
            raise RuntimeError(f"No frames decoded from {source}")
        np.savez_compressed(
            destination, timestamps=np.asarray(timestamps, dtype=np.float64),
            keypoints=np.asarray(keypoints, dtype=np.float32),
            bbox=np.asarray(boxes, dtype=np.float32),
            track_id=np.asarray(track_ids, dtype=np.int64),
            video_id=np.asarray(str(row.video_id)), dataset=np.asarray(str(row.dataset)),
            subject=np.asarray(str(row.subject)), source_path=np.asarray(str(source)),
            pose_model=np.asarray(str(args.model)))
        index_rows.append({"video_id": row.video_id, "cache_path": str(destination),
                           "source_path": str(source), "status": "created"})
    pd.DataFrame(index_rows).to_csv(args.output_dir / "index.csv", index=False)


if __name__ == "__main__":
    main()
