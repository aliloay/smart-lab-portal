"""ONNX + OpenCV DNN (what the backend runs) vs Ultralytics on the same pictures (2026-10-29):
    py parity_bin.py <best.pt> <best.onnx>   (run with the BACKEND venv's OpenCV for the dnn side)"""
import glob, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))
import cv2
from ultralytics import YOLO
from app.services import bin_detector as bd

pt, onnx = sys.argv[1:3]
bd.MODEL, bd._LOADED, bd.CONF = onnx, False, 0.0
T = 0.6
agree = 0
m = YOLO(pt)
here = os.path.dirname(os.path.abspath(__file__))
pics = glob.glob(os.path.join(here, "data", "bin_r2", "images", "test", "*.jpg")) + glob.glob(os.path.join(here, "data", "smoke_neg", "*"))
dc, db, ts = [], [], []
for p in pics:
    img = cv2.imread(p)
    r = m.predict(img, conf=0.01, imgsz=640, verbose=False)[0]
    c0 = float(r.boxes.conf[0]) if len(r.boxes) else 0.0
    t = time.perf_counter(); d = bd.detect(img); ts.append((time.perf_counter() - t) * 1000)
    c1 = d["confidence"] if d else 0.0
    dc.append(abs(c0 - c1)); agree += (c0 >= T) == (c1 >= T)
    if d and len(r.boxes) and c0 >= T:
        x1, y1, x2, y2 = r.boxes.xyxyn[0].tolist(); b = d["box"]
        db.append(max(abs(x1 - b["x"]), abs(y1 - b["y"]), abs(x2 - b["x"] - b["w"]), abs(y2 - b["y"] - b["h"])))
ts.sort()
print(f"{len(pics)} pictures | max confidence difference {max(dc):.3f} | max box edge difference {max(db) if db else 0:.3f} of the frame"
      f" | same bin/no-bin call at {T}: {agree}/{len(pics)} | {bd.engine()} p50 {ts[len(ts)//2]:.0f} ms p95 {ts[int(.95*(len(ts)-1))]:.0f} ms")
