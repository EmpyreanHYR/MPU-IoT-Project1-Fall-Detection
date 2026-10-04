#!/usr/bin/env python3
"""Obtain the official YOLOv8s-pose weights and export the CPU runtime format."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("data/models"))
    args=parser.parse_args()
    from ultralytics import YOLO
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    weights=output/"yolov8s-pose.pt"
    url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s-pose.pt"
    if not weights.exists():
        temporary=weights.with_suffix(".download")
        try:
            with urlopen(url,timeout=60) as response,temporary.open("wb") as target:
                while chunk:=response.read(1024*1024):target.write(chunk)
            temporary.replace(weights)
        finally:temporary.unlink(missing_ok=True)
    model=YOLO(str(weights))
    result=Path(model.export(format="onnx",opset=17,imgsz=640,batch=1,
                            dynamic=False,simplify=False,nms=False,device="cpu"))
    metadata={"source":url,"pose_model":"yolov8s-pose","imgsz":640,
              "license":"See the upstream Ultralytics license; not relicensed by this project.",
              "sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (weights,result)}}
    (output/"pose_model.provenance.json").write_text(json.dumps(metadata,indent=2)+"\n")
    print(f"CPU pose model: {result}")


if __name__=="__main__":main()
