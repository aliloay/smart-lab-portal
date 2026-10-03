# Person detector and re-identification (not in git)

| File | Purpose | Source | SHA-256 |
|---|---|---|---|
| `object_detection_yolox_2022nov.onnx` | YOLOX-S, 80 COCO classes (person = 0), 36 MB | https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` |
| `person_reid_youtu_2021nov.onnx` | Person re-identification (Youtu), 768-d body embedding, 107 MB - optional: the identity lock uses colours only without it | https://github.com/opencv/opencv_zoo/raw/main/models/person_reid_youtureid/person_reid_youtu_2021nov.onnx | `0579683334d4b9440221606dcb461656dd0dc64143b18f48faedaced9b4f580d` |

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
