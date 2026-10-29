"""The full bin test through the backend's own detector code (app/services/bin_detector.py + ONNX Runtime), i.e.
exactly what /scan/appearance runs (2026-10-29):   py eval_deployed.py <model.onnx> [conf=0.6]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
from app.services import bin_detector as bd
from eval_bin import NEG, POS, iou, truth
bd.MODEL, bd._LOADED = sys.argv[1], False
bd.CONF = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
hit = sum(1 for p in POS if (d := bd.detect(cv2.imread(p))) and iou((d["box"]["x"], d["box"]["y"], d["box"]["x"] + d["box"]["w"],
          d["box"]["y"] + d["box"]["h"]), truth(p)) >= 0.5)
fp = sum(1 for p in NEG if bd.detect(cv2.imread(p)))
print(f"{os.path.basename(os.path.dirname(os.path.dirname(sys.argv[1])))} conf {bd.CONF}: found {hit}/{len(POS)}  false bins {fp}/{len(NEG)}  ({bd.engine()})")
