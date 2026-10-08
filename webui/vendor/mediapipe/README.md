# Browser pose reference / 浏览器姿态识别参考

`vision_bundle.mjs` and the `wasm/` runtime come from `@mediapipe/tasks-vision@1.0.1` (Apache-2.0). See `LICENSE.apache-2.0.txt` and the [official package](https://www.npmjs.com/package/@mediapipe/tasks-vision).

`pose_landmarker_lite.task` is the versioned [MediaPipe Pose Landmarker Lite model](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) recommended by the [official browser guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js).

The browser loads these assets from the authenticated FallGuard service.
Precompressed `.wasm.gz` files reduce first-load bandwidth when the browser
advertises gzip support. Pose extraction runs on the viewer's device. In the
browser demonstration, the extracted landmarks are sent to the backend for
fall classification; camera image frames remain in the browser. The server
adapter maps MediaPipe landmarks to the research classifier's joint order.

This optional browser path is separate from the evaluated Raspberry Pi
YOLOv8s-pose pipeline. The browser demonstration does not contribute to the
reported YOLO-based benchmark or hardware throughput results.
