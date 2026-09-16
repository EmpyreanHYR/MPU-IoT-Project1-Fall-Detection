# Browser pose reference / 浏览器姿态识别参考

`vision_bundle.mjs` and the `wasm/` runtime come from `@mediapipe/tasks-vision@1.0.1` (Apache-2.0). See `LICENSE.apache-2.0.txt` and the [official package](https://www.npmjs.com/package/@mediapipe/tasks-vision).

`pose_landmarker_lite.task` is the versioned [MediaPipe Pose Landmarker Lite model](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) recommended by the [official browser guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js).

The browser loads these assets from the authenticated FallGuard VM. Precompressed `.wasm.gz` files reduce first-load bandwidth; the server sends them only when the browser advertises gzip support. Inference runs on the viewer's device, with no camera frame or local landmarks sent to the VM. This is a pose visualization reference and is separate from the cloud fall-score baseline and research classifier.
