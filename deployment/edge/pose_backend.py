"""Local pose backends. Hailo decoding follows the Hailo AI YOLOv8 pose reference.

Reference: https://github.com/hailo-ai/hailo-apps/tree/main/hailo_apps/python/standalone_apps/pose_estimation
The HEF's UINT16 joint outputs are converted by HailoRT to float32 before decoding.
"""
from contextlib import ExitStack
import time
import cv2
import numpy as np


def letterbox(frame, size=640):
    height, width = frame.shape[:2]
    scale = min(size / width, size / height)
    nw, nh = round(width * scale), round(height * scale)
    left, top = (size - nw) // 2, (size - nh) // 2
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top:top+nh, left:left+nw] = resized
    return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB), scale, left, top


def decode(outputs, confidence=.25):
    """Return highest-scoring person (same selection as the existing Pi sender)."""
    candidates = []
    for size in (80, 40, 20):
        tensors = {v.shape[-1]: v.reshape(size*size, -1) for v in outputs.values()
                   if v.shape[-3:-1] == (size, size)}
        scores = tensors[1][:, 0]
        indices = np.flatnonzero(scores >= confidence)
        if not len(indices):
            continue
        # Selecting the highest-score person is invariant to lower-score NMS suppression.
        index = int(indices[np.argmax(scores[indices])])
        stride = 640 / size
        center = np.array([index % size + .5, index // size + .5]) * stride
        logits = tensors[64][index].reshape(4, 16)
        bins = np.exp(logits - logits.max(-1, keepdims=True))
        distance = (bins / bins.sum(-1, keepdims=True) * np.arange(16)).sum(-1) * stride
        box = np.r_[center-distance[:2], center+distance[2:]]
        joints = tensors[51][index].reshape(17, 3).copy()
        joints[:, :2] = stride * (2*joints[:, :2] - .5) + center
        joints[:, 2] = 1/(1+np.exp(-np.clip(joints[:, 2], -60, 60)))
        candidates.append((float(scores[index]), box, joints))
    return max(candidates, key=lambda x: x[0]) if candidates else None


class HailoPose:
    def __init__(self, model, confidence=.25):
        from pathlib import Path
        if not Path(model).is_file():raise FileNotFoundError('Hailo model not found: '+str(model))
        import hailo_platform as h
        self.stack = ExitStack()
        self.confidence = confidence
        params = h.VDevice.create_params()
        params.scheduling_algorithm = h.HailoSchedulingAlgorithm.ROUND_ROBIN
        self.device = self.stack.enter_context(h.VDevice(params))
        self.model = self.device.create_infer_model(str(model))
        self.model.set_batch_size(1)
        for output in self.model.outputs:
            output.set_format_type(h.FormatType.FLOAT32)
        self.configured = self.stack.enter_context(self.model.configure())
        self.outputs = {o.name: np.empty(o.shape, np.float32) for o in self.model.outputs}
        self.bindings = self.configured.create_bindings(output_buffers=self.outputs)

    def __call__(self, frame):
        began = time.perf_counter()
        image, scale, left, top = letterbox(frame)
        self.bindings.input().set_buffer(image)
        start = time.perf_counter()
        self.configured.run([self.bindings], timeout=10000)
        infer_ms = (time.perf_counter()-start)*1000
        result = decode(self.outputs, self.confidence)
        points, box_confidence = np.zeros((17, 3), np.float32), 0.
        if result:
            box_confidence, _, points = result
            points[:, 0] = (points[:, 0]-left)/scale/frame.shape[1]
            points[:, 1] = (points[:, 1]-top)/scale/frame.shape[0]
            points = np.clip(points, 0, 1).astype(np.float32)
        return points, box_confidence, {'pose_ms': (time.perf_counter()-began)*1000,
                                       'accelerator_ms': infer_ms}

    def close(self):
        self.stack.close()


class CpuPose:
    def __init__(self, model, confidence=.25):
        from pathlib import Path
        if not Path(model).is_file():
            raise FileNotFoundError('CPU weights must be installed locally before offline use: '+str(model))
        self.onnx=str(model).endswith('.onnx')
        if self.onnx:
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
            self.session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
            self.confidence=confidence
            return
        from ultralytics import YOLO
        import torch
        torch.set_num_threads(4)
        self.model = YOLO(str(model))
        self.confidence = confidence

    def __call__(self, frame):
        began = time.perf_counter()
        image, scale, left, top = letterbox(frame)
        if self.onnx:
            tensor=np.ascontiguousarray(image.transpose(2,0,1)[None],dtype=np.float32)/255.
            predictions=self.session.run(None,{self.session.get_inputs()[0].name:tensor})[0][0].T
            best=predictions[int(np.argmax(predictions[:,4]))]
            points=np.zeros((17,3),np.float32);box_confidence=0.
            if best[4]>=self.confidence:
                box_confidence=float(best[4]);points=best[5:].reshape(17,3).copy()
                points[:,0]=(points[:,0]-left)/scale/frame.shape[1]
                points[:,1]=(points[:,1]-top)/scale/frame.shape[0]
                points=np.clip(points,0,1)
            return points,box_confidence,{'pose_ms':(time.perf_counter()-began)*1000}
        result = self.model.predict(cv2.cvtColor(image, cv2.COLOR_RGB2BGR), imgsz=640,
                                    conf=self.confidence, device='cpu', verbose=False)[0]
        points, box_confidence = np.zeros((17, 3), np.float32), 0.
        if result.keypoints is not None and len(result.boxes):
            index = int(result.boxes.conf.argmax())
            box_confidence = float(result.boxes.conf[index])
            points = result.keypoints.data[index].cpu().numpy().copy()
            points[:, 0] = (points[:, 0]-left)/scale/frame.shape[1]
            points[:, 1] = (points[:, 1]-top)/scale/frame.shape[0]
            points = np.clip(points, 0, 1)
        return points, box_confidence, {'pose_ms': (time.perf_counter()-began)*1000}

    def close(self):
        pass


def annotate(frame, points, probability=None):
    image = frame.copy()
    pixels = points[:, :2] * np.array([image.shape[1], image.shape[0]])
    for a,b in [(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),
                (11,13),(13,15),(12,14),(14,16)]:
        if points[a,2]>=.2 and points[b,2]>=.2:
            cv2.line(image, tuple(pixels[a].astype(int)), tuple(pixels[b].astype(int)), (0,210,0), 2)
    for point,pixel in zip(points,pixels):
        if point[2]>=.2: cv2.circle(image,tuple(pixel.astype(int)),3,(0,80,255),-1)
    if probability is not None:
        cv2.putText(image,f'Local fall probability: {probability:.3f}',(12,26),
                    cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
    return image
