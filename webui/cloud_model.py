"""Cloud-side inference for the pretrained 30-frame fall Transformer."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import json
import math
import re
import threading
import time

import numpy as np
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    Interpreter = None

try:
    import onnxruntime as ort
except ImportError:  # The original TFLite deployment remains usable without ONNX Runtime.
    ort = None


MODEL_NAME = "Punpayut Transformer TFLite / 云端预训练模型"
DEFAULT_MODEL_ID = "punpayut_transformer_tflite"
MODEL_SHA256 = "c66659c3ac6d37c60469bee4d6f88cb2ac4976928bde6d46b19e7f851e8980b0"
TIMESTEPS = 30
FEATURES = 51
FALL_THRESHOLD = 0.90
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,80}$")

# The upstream model alphabetically sorts these names before flattening x/y/visibility.
SORTED_NAMES = sorted([
    "Nose", "Left Eye", "Right Eye", "Left Ear", "Right Ear",
    "Left Shoulder", "Right Shoulder", "Left Elbow", "Right Elbow",
    "Left Wrist", "Right Wrist", "Left Hip", "Right Hip",
    "Left Knee", "Right Knee", "Left Ankle", "Right Ankle",
])
NAME_TO_MP_INDEX = {
    "Nose": 0, "Left Eye": 2, "Right Eye": 5, "Left Ear": 7, "Right Ear": 8,
    "Left Shoulder": 11, "Right Shoulder": 12, "Left Elbow": 13, "Right Elbow": 14,
    "Left Wrist": 15, "Right Wrist": 16, "Left Hip": 23, "Right Hip": 24,
    "Left Knee": 25, "Right Knee": 26, "Left Ankle": 27, "Right Ankle": 28,
}
COCO_MP_INDICES = (0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)


def _number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def validate_landmarks(raw: object) -> list[list[float]]:
    if not isinstance(raw, list) or len(raw) not in (0, 33):
        raise ValueError("landmarks must contain 33 MediaPipe points or be empty")
    points: list[list[float]] = []
    for index, point in enumerate(raw):
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError(f"landmarks[{index}] must be [x, y, visibility]")
        points.append([
            _number(point[0], f"landmarks[{index}].x", -0.5, 1.5),
            _number(point[1], f"landmarks[{index}].y", -0.5, 1.5),
            _number(point[2], f"landmarks[{index}].visibility", 0, 1),
        ])
    return points


def _tflite_feature_frame(points: list[list[float]]) -> np.ndarray:
    features = np.zeros(FEATURES, dtype=np.float32)
    if points:
        for position, name in enumerate(SORTED_NAMES):
            features[position * 3:position * 3 + 3] = points[NAME_TO_MP_INDEX[name]]

    positions = {name: SORTED_NAMES.index(name) * 3 for name in SORTED_NAMES}
    def landmark(name: str) -> tuple[float, float, float]:
        start = positions[name]
        return float(features[start]), float(features[start + 1]), float(features[start + 2])

    left_shoulder, right_shoulder = landmark("Left Shoulder"), landmark("Right Shoulder")
    left_hip, right_hip = landmark("Left Hip"), landmark("Right Hip")
    def midpoint(first: tuple[float, float, float], second: tuple[float, float, float]):
        valid_first, valid_second = first[2] > 0.3, second[2] > 0.3
        if valid_first and valid_second:
            return (first[0] + second[0]) / 2, (first[1] + second[1]) / 2
        if valid_first:
            return first[0], first[1]
        if valid_second:
            return second[0], second[1]
        return None

    mid_shoulder, mid_hip = midpoint(left_shoulder, right_shoulder), midpoint(left_hip, right_hip)
    if mid_hip is None:
        return features
    reference_height = abs(mid_shoulder[1] - mid_hip[1]) if mid_shoulder is not None else 0.0
    for position in range(0, FEATURES, 3):
        features[position] -= mid_hip[0]
        features[position + 1] -= mid_hip[1]
        if reference_height >= 1e-5:
            features[position] /= reference_height
            features[position + 1] /= reference_height
    return features


def _course_feature_frame(points: list[list[float]]) -> np.ndarray:
    """Match the course experiment: COCO body12, per-frame min-max, confidence."""
    features = np.zeros((12, 3), dtype=np.float32)
    if points:
        coco = np.asarray([points[index] for index in COCO_MP_INDICES], dtype=np.float32)
        features = coco[5:17].copy()
        for axis in (0, 1):
            values = features[:, axis]
            lower, upper = float(values.min()), float(values.max())
            features[:, axis] = (values - lower) / max(upper - lower, 1e-4)
        features[:, 2] = np.clip(features[:, 2], 0, 1)
    return features.reshape(36)


def coco_points(points: list[list[float]]) -> list[list[float]]:
    if not points:
        return []
    return [[max(0.0, min(1.0, points[i][0])), max(0.0, min(1.0, points[i][1])), points[i][2]] for i in COCO_MP_INDICES]


def mediapipe_points_from_coco(points: list[list[float]]) -> list[list[float]]:
    """Place 17 COCO points into the equivalent MediaPipe landmark slots."""
    if len(points) != 17:
        raise ValueError("COCO pose must contain 17 points")
    result = [[0.0, 0.0, 0.0] for _ in range(33)]
    for coco_index, mediapipe_index in enumerate(COCO_MP_INDICES):
        point = points[coco_index]
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("each COCO point must be [x, y, confidence]")
        result[mediapipe_index] = [float(point[0]), float(point[1]), float(point[2])]
    return result


class CloudFallModel:
    def __init__(self, model_path: Path, course_root: Path | None = None, quality_path: Path | None = None) -> None:
        self.model_path = model_path
        self.models = {}
        if Interpreter is not None and model_path.is_file():
            interpreter = Interpreter(model_path=str(model_path), num_threads=2)
            interpreter.allocate_tensors()
            input_detail = interpreter.get_input_details()[0]
            output_detail = interpreter.get_output_details()[0]
            if tuple(input_detail["shape"]) != (1, TIMESTEPS, FEATURES):
                raise RuntimeError(f"unexpected model input shape: {input_detail['shape']}")
            self.models: dict[str, dict] = {
                DEFAULT_MODEL_ID: {
                    "id": DEFAULT_MODEL_ID, "name_en": "Punpayut Transformer TFLite",
                    "name_zh": "Punpayut 预训练 Transformer", "model": MODEL_NAME,
                    "state_model": "Punpayut Transformer TFLite",
                    "source": "Public pretrained reference / 公开预训练参考模型",
                    "purpose_en": "Reference model for the original 17-keypoint TFLite pipeline.",
                    "purpose_zh": "用于原始 17 关键点 TFLite 流程的公开参考模型。",
                    "architecture": "transformer_tflite", "trained_at": "upstream release",
                    "live_available": True, "input_shape": [1, 30, 51],
                    "fall_threshold": FALL_THRESHOLD, "runtime": "LiteRT CPU",
                    "sha256": MODEL_SHA256, "feature_format": "punpayut17",
                    "runtime_model": interpreter, "input_detail": input_detail,
                    "output_detail": output_detail,
                }
            }
        self._load_course_models(course_root)
        if quality_path is not None and quality_path.is_file() and ort is not None:
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
            runtime=ort.InferenceSession(str(quality_path),sess_options=options,providers=['CPUExecutionProvider'])
            if {x.name for x in runtime.get_inputs()} != {'pose','quality'}:
                raise RuntimeError('Selected classifier must have pose and quality inputs')
            self.models['masked_bimamba_quality']={'id':'masked_bimamba_quality','name_en':'MaskedBiMamba quality (current)',
                'name_zh':'当前双输入 MaskedBiMamba','model':'MaskedBiMamba quality / 当前双输入模型',
                'state_model':'MaskedBiMamba browser demo','source':'Current selected project classifier / 当前项目选定权重',
                'purpose_en':'Browser-camera demonstration; MediaPipe pose differs from the evaluated YOLO pipeline.',
                'purpose_zh':'电脑摄像头演示；MediaPipe姿态来源不同于论文实测YOLO链路。',
                'live_available':True,'input_shape':[1,30,36],'fall_threshold':.82,'runtime':'ONNX Runtime CPU',
                'sha256':__import__('hashlib').sha256(quality_path.read_bytes()).hexdigest(),
                'feature_format':'body12_quality','runtime_model':runtime}
        if not any(x.get('live_available') for x in self.models.values()):
            raise RuntimeError('No browser inference model is available')
        self.lock = threading.RLock()
        self.sessions: dict[str, dict] = {}
        preferred = "masked_bimamba_quality" if "masked_bimamba_quality" in self.models else "fallguard_masked_bimamba"
        self.active_model_id = preferred if self.models.get(preferred, {}).get("live_available") else DEFAULT_MODEL_ID

    def _load_course_models(self, course_root: Path | None) -> None:
        if course_root is None or not (course_root / "catalog.json").is_file():
            return
        catalog = json.loads((course_root / "catalog.json").read_text(encoding="utf-8"))
        for raw in catalog.get("models", []):
            item = dict(raw)
            item["fall_threshold"] = float(item.pop("threshold", 0.5))
            item["model"] = f"{item['name_en']} / {item['name_zh']}"
            item["state_model"] = item["name_en"]
            item["feature_format"] = "course_body12"
            item["runtime"] = "ONNX Runtime CPU" if item.get("live_available") else "PyTorch checkpoint archive"
            onnx_name = item.pop("onnx", None)
            item.pop("checkpoint", None)
            if item.get("live_available"):
                if ort is None or not onnx_name or not (course_root / "artifacts" / onnx_name).is_file():
                    item["live_available"] = False
                    item["unavailable_reason"] = "ONNX Runtime is not installed"
                else:
                    path = course_root / "artifacts" / onnx_name
                    options = ort.SessionOptions()
                    options.intra_op_num_threads = 2
                    options.inter_op_num_threads = 1
                    item["runtime_model"] = ort.InferenceSession(
                        str(path), sess_options=options, providers=["CPUExecutionProvider"])
                    item["sha256"] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            self.models[item["id"]] = item

    @staticmethod
    def _public_model(item: dict) -> dict:
        hidden = {"runtime_model", "input_detail", "output_detail", "feature_format", "state_model"}
        return {key: value for key, value in item.items() if key not in hidden}

    def info(self) -> dict:
        return {
            "available": True, "model": self.models[self.active_model_id]["model"], "sha256": self.models[self.active_model_id]["sha256"],
            "input_shape": self.models[self.active_model_id]["input_shape"], "fall_threshold": self.models[self.active_model_id]["fall_threshold"],
            "inference_location": "cloud", "feature_source": "browser MediaPipe landmarks",
            "default_model_id": self.active_model_id,
            "active_model_id": self.active_model_id,
            "models": [self._public_model(item) for item in self.models.values()],
        }

    def select_model(self, model_id: str) -> dict:
        selected = self.models.get(model_id)
        if selected is None or not selected.get("live_available") or "runtime_model" not in selected:
            raise ValueError("selected model is not available for live inference")
        with self.lock:
            self.active_model_id = model_id
        return {"selected": True, "model_id": model_id, "model": selected["model"]}

    def reset(self, session_id: str) -> None:
        with self.lock:
            for key in [key for key in self.sessions if key.startswith(session_id + ":")]:
                self.sessions.pop(key, None)

    def add_frame(self, session_id: str, frame_seq: int, points: list[list[float]],
                  model_id: str | None = None) -> dict:
        if not SESSION_PATTERN.fullmatch(session_id):
            raise ValueError("session_id is invalid")
        if isinstance(frame_seq, bool) or not isinstance(frame_seq, int) or not 0 <= frame_seq <= 2**53:
            raise ValueError("frame_seq must be a nonnegative integer")
        model_id = model_id or self.active_model_id
        selected = self.models.get(model_id)
        if selected is None:
            raise ValueError("model_id is invalid")
        if not selected.get("live_available") or "runtime_model" not in selected:
            raise ValueError("selected model is not available for live inference")
        now = time.time()
        session_key = f"{session_id}:{model_id}"
        with self.lock:
            for key in [key for key, value in self.sessions.items() if now - value["updated"] > 120]:
                self.sessions.pop(key, None)
            if session_key not in self.sessions and len(self.sessions) >= 8:
                oldest = min(self.sessions, key=lambda key: self.sessions[key]["updated"])
                self.sessions.pop(oldest, None)
            session = self.sessions.setdefault(session_key, {"frames": deque(maxlen=TIMESTEPS), "updated": now, "last_seq": -1, "times": deque(maxlen=TIMESTEPS)})
            if frame_seq <= session["last_seq"]:
                raise ValueError("frame_seq must increase")
            session["last_seq"], session["updated"] = frame_seq, now
            if selected["feature_format"] == "body12_quality":
                body=np.asarray([points[i] for i in COCO_MP_INDICES[5:]],dtype=np.float32) if points else np.zeros((12,3),np.float32)
                valid=(body[:,2]>.2).sum()>=6
                if not valid:
                    session['frames'].clear();session['times'].clear()
                    return {'ready':False,'frames_collected':0,'frames_required':5,'reason':'no_valid_pose'}
                if session['times'] and now-session['times'][-1]>.75:
                    session['frames'].clear();session['times'].clear()
                session['frames'].append(body);session['times'].append(now)
                result={'ready':False,'frames_collected':len(session['frames']),'frames_required':5,
                        'model':selected['model'],'state_model':selected['state_model'],'model_id':model_id}
                if now-session['times'][0]<1.:return result
                raw=np.stack(session['frames']);times=np.asarray(session['times']);target=np.linspace(now-1.,now,30,endpoint=False)
                flat=raw.reshape(len(raw),36)
                sampled=np.stack([np.interp(target,times,flat[:,i]) for i in range(36)],axis=1).reshape(30,12,3)
                # MediaPipe has joint visibility but no YOLO box score. Its mean
                # visibility supplies that input for this explicitly labeled demo.
                quality=np.stack([sampled[:,:,2].mean(1),(sampled[:,:,2]>=.2).mean(1),sampled[:,:,2].mean(1)],axis=1).astype(np.float32)
                for axis in (0,1):
                    values=sampled[:,:,axis];lo=values.min(1,keepdims=True)
                    sampled[:,:,axis]=(values-lo)/np.maximum(values.max(1,keepdims=True)-lo,1e-4)
                began=time.perf_counter()
                logits=selected['runtime_model'].run(None,{'pose':sampled.reshape(1,30,36).astype(np.float32),'quality':quality[None]})[0][0]
                exp=np.exp(logits-logits.max());prob=float(exp[1]/exp.sum())
                result.update(ready=True,fall_probability=round(prob,5),label='fall' if prob>=selected['fall_threshold'] else 'no_fall',inference_ms=round((time.perf_counter()-began)*1000,2))
                return result
            feature = (_tflite_feature_frame(points) if selected["feature_format"] == "punpayut17"
                       else _course_feature_frame(points))
            session["frames"].append(feature)
            collected = len(session["frames"])
            result = {"ready": False, "frames_collected": collected, "frames_required": TIMESTEPS,
                      "model": selected["model"], "state_model": selected["state_model"], "model_id": model_id}
            if collected < TIMESTEPS:
                return result
            tensor = np.expand_dims(np.asarray(session["frames"], dtype=np.float32), axis=0)
            started = time.perf_counter()
            if selected["feature_format"] == "punpayut17":
                runtime = selected["runtime_model"]
                runtime.set_tensor(selected["input_detail"]["index"], tensor)
                runtime.invoke()
                probability = float(runtime.get_tensor(selected["output_detail"]["index"])[0][0])
            else:
                runtime = selected["runtime_model"]
                logits = runtime.run(["logits"], {"pose": tensor})[0][0]
                shifted = logits - np.max(logits)
                probability = float(np.exp(shifted)[1] / np.exp(shifted).sum())
            threshold = float(selected["fall_threshold"])
            result.update({
                "ready": True, "fall_probability": round(max(0.0, min(1.0, probability)), 5),
                "label": "fall" if probability >= threshold else "no_fall",
                "inference_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return result

    def add_coco_frame(self, device_id: str, frame_seq: int,
                       points: list[list[float]]) -> dict:
        session_id = ("pi_" + re.sub(r"[^A-Za-z0-9_-]", "_", device_id))[:80]
        if len(session_id) < 12:
            session_id = (session_id + "_fallguard_pi")[:12]
        return self.add_frame(session_id, frame_seq,
                              mediapipe_points_from_coco(points), self.active_model_id)
