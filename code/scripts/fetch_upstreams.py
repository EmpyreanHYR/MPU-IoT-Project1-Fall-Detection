#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned reference implementations.")
    parser.add_argument("--name", choices=("tcnte", "fall_mamba", "all"), default="all")
    parser.add_argument("--destination", type=Path,
                        default=Path(__file__).resolve().parents[1] / "third_party" / "upstream")
    args = parser.parse_args()
    lock_path = Path(__file__).resolve().parents[1] / "third_party" / "upstreams.json"
    with lock_path.open("r", encoding="utf-8") as handle:
        upstreams = json.load(handle)
    names = list(upstreams) if args.name == "all" else [args.name]
    args.destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        spec = upstreams[name]
        target = args.destination / name
        if not target.exists():
            subprocess.run(["git", "clone", "--no-checkout", spec["url"], str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "fetch", "origin", spec["commit"], "--depth", "1"], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", spec["commit"]], check=True)
        actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        if actual != spec["commit"]:
            raise RuntimeError(f"Commit mismatch for {name}: {actual}")
        print(name, actual, target)


if __name__ == "__main__":
    main()

