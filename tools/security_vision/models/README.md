# Person detector and re-identification (not in git)

| File | Purpose | Source | SHA-256 |
|---|---|---|---|
| `object_detection_yolox_2022nov.onnx` | YOLOX-S, 80 COCO classes (person = 0), 36 MB | https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` |
| `person_reid_youtu_2021nov.onnx` | Person re-identification (Youtu), 768-d body embedding, 107 MB - optional: the identity lock uses colours only without it | https://github.com/opencv/opencv_zoo/raw/main/models/person_reid_youtureid/person_reid_youtu_2021nov.onnx | `0579683334d4b9440221606dcb461656dd0dc64143b18f48faedaced9b4f580d` |
| `yolo26s_544x960.onnx` | **Default since 2026-10-26.** YOLO26s (Ultralytics, AGPL-3.0) at the analysis frame's own size 544x960 (no square letterbox); raw 84 x N head, NMS in vision.py | exported from the official `yolo26s.pt` with ultralytics 8.4.188: `YOLO("yolo26s.pt").export(format="onnx", imgsz=(544, 960), opset=17, simplify=True, end2end=False)` | `eb250ecd39017abc214890400a6c304b6c9f852a378c242d1f2a5cff75dfa054` |
| `yolo26s_416.onnx` | Same weights at 416x416 - zoom crops only (14 ms instead of 38 ms) | same export with `imgsz=416` | `bc109050c25e8d37d421d4d27cb395f63b8089bd78af7660e56bd07f0d369c02` |
| `yolo26s.onnx` | YOLO26s 640x640 - the previous default; still used by the engine tests and as fallback | (2026-10-12) | `e325b36c49c21f6aff2069902f45a3bc94d287027d8a125984f8047b90e45eb5` |

Why these: docs/CV_BENCHMARK_2026-10-26.md (detection on 363 reviewed people, tracking on 3 reviewed clips, two
cameras on the GTX 1650). The export needs PyTorch + ultralytics (an isolated venv, not the camera's Python).

Runs on the CPU through OpenCV's `cv2.dnn` (no PyTorch, no extra package),
from the same OpenCV model zoo as the face models. `start_security_vision.bat`
downloads it on first start; by hand:

```
curl -L -o object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
```

Measured on the development laptop (2026-10-03, 12 threads): 640 px input
~390 ms per frame, 416 px ~160 ms, 320 px ~93 ms. The service uses 416 px,
4 threads, 3 detections a second. Re-identification: ~100 ms per person,
run every frame only while people are close or just apart, else once a second.
