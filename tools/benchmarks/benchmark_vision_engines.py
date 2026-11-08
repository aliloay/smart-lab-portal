#!/usr/bin/env python3
"""Fair inference-only benchmark for Smart Lab's YOLO26 ONNX model.

Engines tested (when available):
  1) ONNX Runtime DirectML
  2) OpenVINO CPU
  3) ONNX Runtime CPU

The script is read-only: it does not modify the project or restart SecurityCam.
All engines receive the same deterministic synthetic float32 input tensor. This
measures inference only, not camera capture, preprocessing, tracking, face
recognition, network latency, or browser rendering.

Run from the Smart Lab project root:
  python benchmark_vision_engines.py

Options:
  python benchmark_vision_engines.py --iterations 100 --warmup 10
  python benchmark_vision_engines.py --model path\\to\\model.onnx
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path
from typing import Callable, Any
import numpy as np


def summarize(name: str, samples: list[float]) -> dict[str, float | str | int]:
    a = np.asarray(samples, dtype=np.float64)
    median = float(np.median(a))
    return {
        "engine": name,
        "n": len(samples),
        "mean": float(a.mean()),
        "median": median,
        "p95": float(np.percentile(a, 95)),
        "min": float(a.min()),
        "max": float(a.max()),
        "fps": 1000.0 / median if median > 0 else float("inf"),
    }


def print_row(row: dict[str, float | str | int]) -> None:
    print(
        f"{str(row['engine']):<25} n={int(row['n']):>3}  "
        f"mean={float(row['mean']):>8.2f} ms  "
        f"median={float(row['median']):>8.2f} ms  "
        f"p95={float(row['p95']):>8.2f} ms  "
        f"min={float(row['min']):>8.2f} ms  "
        f"max={float(row['max']):>8.2f} ms  "
        f"median-FPS≈{float(row['fps']):>7.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=str(Path(__file__).resolve().parent / "tools" / "security_vision" / "models" / "yolo26s.onnx"),
        help="Path to the same YOLO26 ONNX model used by SecurityCam.",
    )
    parser.add_argument("--iterations", type=int, default=100, help="Timed calls per engine (default: 100).")
    parser.add_argument("--warmup", type=int, default=10, help="Untimed warm-up calls per engine (default: 10).")
    args = parser.parse_args()
    if args.iterations < 20:
        print("ERROR: use at least 20 timed iterations; 100 is recommended.")
        return 2
    if args.warmup < 0:
        print("ERROR: --warmup cannot be negative.")
        return 2

    model_path = Path(args.model).resolve()
    if not model_path.is_file():
        print(f"ERROR: model file not found: {model_path}")
        print("Run from the Smart Lab project root, or pass --model with the correct path.")
        return 2

    print("Smart Lab YOLO26 inference benchmark")
    print(f"Model: {model_path}")
    print(f"Timed calls per engine: {args.iterations}; warm-up calls: {args.warmup}")
    print("Input: deterministic synthetic float32 tensor; identical values for each engine.")
    print("This measures inference only; it does not evaluate detection accuracy or camera-to-screen latency.\n")

    try:
        import onnxruntime as ort
    except Exception as exc:
        print(f"ERROR: ONNX Runtime import failed: {type(exc).__name__}: {exc}")
        return 2
    print(f"ONNX Runtime version: {ort.__version__}")
    print(f"Available ONNX Runtime providers: {ort.get_available_providers()}")

    # Inspect the ONNX input via CPU to get its stable name/type/shape.
    try:
        inspect_opts = ort.SessionOptions()
        inspect_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        inspect_session = ort.InferenceSession(str(model_path), sess_options=inspect_opts, providers=["CPUExecutionProvider"])
        ort_input = inspect_session.get_inputs()[0]
        input_name = ort_input.name
        raw_shape = ort_input.shape
        target_shape = [1, 3, 640, 640]
        shape: list[int] = []
        for i, dim in enumerate(raw_shape):
            shape.append(int(dim) if isinstance(dim, int) and dim > 0 else target_shape[i])
        input_type = ort_input.type
        del inspect_session
        if shape != target_shape:
            print(f"ERROR: expected input shape {target_shape}; model reports {shape}. Stopping rather than comparing different shapes.")
            return 2
        if input_type != "tensor(float)":
            print(f"ERROR: expected float32 model input; model reports {input_type}.")
            return 2
    except Exception as exc:
        print(f"ERROR: model inspection failed: {type(exc).__name__}: {exc}")
        return 2

    print(f"Input: {input_name}; shape={shape}; type={input_type}")
    rng = np.random.default_rng(20261013)
    tensor = rng.random(shape, dtype=np.float32)

    engines: list[dict[str, Any]] = []

    # DirectML uses sequential execution with memory-pattern optimization disabled.
    if "DmlExecutionProvider" in ort.get_available_providers():
        try:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.enable_mem_pattern = False
            t0 = time.perf_counter()
            sess = ort.InferenceSession(
                str(model_path), sess_options=opts,
                providers=["DmlExecutionProvider", "CPUExecutionProvider"],
            )
            setup_ms = (time.perf_counter() - t0) * 1000
            name = sess.get_inputs()[0].name
            engines.append({
                "name": "ONNX Runtime DirectML",
                "run": lambda s=sess, n=name: s.run(None, {n: tensor}),
                "providers": sess.get_providers(),
                "setup_ms": setup_ms,
            })
        except Exception as exc:
            print(f"SKIP DirectML: {type(exc).__name__}: {exc}")
    else:
        print("SKIP DirectML: DmlExecutionProvider is not available.")

    # OpenVINO CPU, using the same ONNX file and tensor.
    try:
        import openvino as ov
        t0 = time.perf_counter()
        core = ov.Core()
        ov_model = core.read_model(str(model_path))
        ov_input_name = ov_model.input(0).get_any_name()
        compiled = core.compile_model(ov_model, "CPU", {"PERFORMANCE_HINT": "LATENCY"})
        request = compiled.create_infer_request()
        setup_ms = (time.perf_counter() - t0) * 1000
        def run_openvino(req=request, name=ov_input_name):
            result = req.infer({name: tensor})
            return list(result.values())
        engines.append({
            "name": "OpenVINO CPU", "run": run_openvino,
            "providers": ["OpenVINO CPU"], "setup_ms": setup_ms,
        })
        print(f"OpenVINO version: {ov.__version__}")
    except Exception as exc:
        print(f"SKIP OpenVINO CPU: {type(exc).__name__}: {exc}")

    # ONNX Runtime CPU baseline.
    try:
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        t0 = time.perf_counter()
        sess = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        setup_ms = (time.perf_counter() - t0) * 1000
        name = sess.get_inputs()[0].name
        engines.append({
            "name": "ONNX Runtime CPU",
            "run": lambda s=sess, n=name: s.run(None, {n: tensor}),
            "providers": sess.get_providers(), "setup_ms": setup_ms,
        })
    except Exception as exc:
        print(f"SKIP ONNX Runtime CPU: {type(exc).__name__}: {exc}")

    if len(engines) < 2:
        print("\nERROR: fewer than two engines initialized; no comparison is possible.")
        return 2

    print("\nEngine initialization (setup time is NOT included in inference latency):")
    for e in engines:
        print(f"  {e['name']}: configured providers={e['providers']}; setup/compile={e['setup_ms']:.1f} ms")

    # Warm up, then ensure each engine can return finite outputs.
    healthy: list[dict[str, Any]] = []
    print("\nWarm-up (not timed):")
    for e in engines:
        try:
            for _ in range(args.warmup):
                e["run"]()
            e["last_outputs"] = e["run"]()
            outputs = [np.asarray(x) for x in e["last_outputs"]]
            if not all(np.isfinite(x).all() for x in outputs):
                raise ValueError("one or more output tensors contain NaN/Inf")
            healthy.append(e)
            print(f"  OK: {e['name']}")
        except Exception as exc:
            print(f"  FAILED: {e['name']}: {type(exc).__name__}: {exc}")
    engines = healthy
    if len(engines) < 2:
        print("\nERROR: fewer than two engines passed warm-up; no comparison is possible.")
        return 2

    print("\nOutput check (synthetic input; not accuracy validation):")
    base = [np.asarray(x) for x in engines[0]["last_outputs"]]
    print(f"  Reference engine: {engines[0]['name']}; output shapes={[x.shape for x in base]}")
    for e in engines[1:]:
        other = [np.asarray(x) for x in e["last_outputs"]]
        if len(base) != len(other) or any(a.shape != b.shape for a, b in zip(base, other)):
            print(f"  {e['name']}: output count/shape mismatch")
        else:
            diffs = [float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64)))) for a, b in zip(base, other) if a.size]
            print(f"  {e['name']}: matching shapes; max absolute difference={max(diffs) if diffs else 0:.6g}")

    names = [str(e["name"]) for e in engines]
    run_by_name: dict[str, Callable[[], Any]] = {str(e["name"]): e["run"] for e in engines}
    samples: dict[str, list[float]] = {name: [] for name in names}
    print(f"\nTimed benchmark: {args.iterations} samples per engine, order rotated per sample...")
    try:
        for i in range(args.iterations):
            offset = i % len(names)
            order = names[offset:] + names[:offset]
            for name in order:
                t0 = time.perf_counter()
                run_by_name[name]()
                samples[name].append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        print(f"\nERROR during timed inference: {type(exc).__name__}: {exc}")
        return 2

    print("\nRESULTS — lower is better")
    print("Engine                    n       mean     median       p95       min       max   median-FPS")
    rows = [summarize(name, samples[name]) for name in names]
    for row in rows:
        print_row(row)
    best = min(rows, key=lambda row: float(row["median"]))
    print(f"\nFastest median in this run: {best['engine']} — {float(best['median']):.2f} ms (~{float(best['fps']):.2f} inferences/s).")
    print("\nLIMITATIONS:")
    print("- DirectML's configured provider list does not prove every ONNX node executes on the GPU; unsupported nodes may fall back to CPU.")
    print("- Synthetic inputs benchmark inference only. They do not prove person-detection accuracy or real-camera performance.")
    print("- These numbers exclude camera decode, preprocessing, postprocessing, tracking, ReID, face recognition, HTTP and browser rendering.")
    print("- Do not switch the live SecurityCam engine based only on this test; validate with identical real frames and end-to-end timings first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
