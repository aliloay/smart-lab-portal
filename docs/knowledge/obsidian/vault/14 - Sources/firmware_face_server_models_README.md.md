---
type: "source-mirror"
source_kind: "documentation"
source_path: "firmware/face_server/models/README.md"
source_hash: "9a59fe3fbb3a8960252b9e9f8924a7e4d03eefb3015b1a39fb0e2808db9bd3fb"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/face_server/models/README.md` - edit the original in the repository, not this note.

Systems: [[Door and access]]

# Face models (not in git — 39 MB)

Downloaded once from the OpenCV model zoo; the `.onnx` files are gitignored.

| File | Purpose | Source | SHA-256 |
|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` | YuNet face detector (box + 5 landmarks) | https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `face_recognition_sface_2021dec.onnx` | SFace recognizer (128-d embedding) | https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

Both run on the CPU through OpenCV ≥ 4.8 (`cv2.FaceDetectorYN`,
`cv2.FaceRecognizerSF`); no extra Python package. To fetch them (needs
internet once):

```
cd firmware/face_server/models
curl -L -O https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L -O https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

Compare them with the current LBPH recognizer on the enrolled samples:
`py firmware/tools/eval_face_models.py`.

