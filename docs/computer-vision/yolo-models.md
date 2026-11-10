# YOLO and detection models

| Model | Purpose | Where | Format | Source / licence |
|---|---|---|---|---|
| `yolo26s_544x960.onnx` | **Default person detector** (since 26 Oct 2026), at the analysis frame's own size | `tools/security_vision/models/` (not in git, downloaded or exported) | ONNX, raw 84×N head, NMS in `vision.py` | Ultralytics YOLO26s, AGPL-3.0 |
| `yolo26s_416.onnx` | Zoom crops | same | ONNX | same |
| `yolo26s.onnx` | 640×640, previous default and test fallback | same | ONNX | same |
| `object_detection_yolox_2022nov.onnx` | Older CPU fallback | same | ONNX | OpenCV model zoo |
| `person_reid_youtu_2021nov.onnx` | Optional appearance embedding for tracking | same | ONNX | OpenCV model zoo |
| `lab_detector.onnx` | Lab object detector, 12 classes: reusable bin, consumables node, environment node, master node, network switch, router, UR5e, UR5e pendant, FANUC, FANUC pendant, PC, door | `backend/data/models/` (in git, 10.6 MB) | YOLO11n ONNX | Trained in Colab on owner photos; test split mAP50 0.947, mAP50-95 0.839 |
| `bin_detector.onnx`, `all_detector.onnx` | Earlier bin-only and combined models | `backend/data/models/` | ONNX | same pipeline |

Class lists and per-class test results are in [`backend/data/models/detectors.json`](../../backend/data/models/detectors.json). Hashes and export commands for the camera models: [`tools/security_vision/models/README.md`](../../tools/security_vision/models/README.md). Training scripts: [`tools/vision_train/`](../../tools/vision_train/); the training images themselves are kept off GitHub.

Person detection is a **generic class**: YOLO does not identify who a person is.
