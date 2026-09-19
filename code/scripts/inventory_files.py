#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd


VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4", ".webm"}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, object]:
    command = ["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_name,width,height,r_frame_rate",
               "-of", "json", str(path)]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory uploaded data with hashes and video metadata.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hash-all", action="store_true",
                        help="Hash every file; otherwise hash videos and archives only")
    args = parser.parse_args()
    rows: list[dict[str, object]] = []
    archive_extensions = {".zip", ".tar", ".gz", ".zst", ".7z"}
    for path in sorted(item for item in args.root.rglob("*") if item.is_file()):
        suffix = path.suffix.lower()
        is_video = suffix in VIDEO_EXTENSIONS
        should_hash = args.hash_all or is_video or suffix in archive_extensions
        metadata = probe(path) if is_video else {}
        rows.append({
            "path": str(path.resolve()), "relative_path": str(path.relative_to(args.root)),
            "bytes": path.stat().st_size, "suffix": suffix,
            "sha256": sha256(path) if should_hash else "",
            "probe": json.dumps(metadata, ensure_ascii=False),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"files={len(rows)} videos={sum(Path(row['path']).suffix.lower() in VIDEO_EXTENSIONS for row in rows)}")


if __name__ == "__main__":
    main()

