"""Train one bin detector on the data.yaml in the current folder (2026-10-28): py train_bin.py <weights> <name> [epochs=80]"""
import sys
from ultralytics import YOLO
YOLO(sys.argv[1]).train(data='data.yaml', epochs=int(sys.argv[3]) if len(sys.argv) > 3 else 80, imgsz=640, batch=8, device='cpu', workers=0, project='runs',
                        name=sys.argv[2], exist_ok=True, plots=False, verbose=False, seed=0, patience=15,
                        fliplr=0.5, degrees=10, scale=0.6, mosaic=1.0, hsv_v=0.5)
