import os
import sys
import time
from pathlib import Path
import psutil
import numpy as np
import torch
from ultralytics import YOLO

# ----------------- CONFIGURATION -----------------
MODEL_PATH = Path("ai_engine/models/detection/yolo11s.pt")
DEVICE = 0 if torch.cuda.is_available() else "cpu"
WARMUP_ITERATIONS = 15
BENCHMARK_ITERATIONS = 60
RESOLUTIONS = [
    ("Default YOLO (640x640)", (640, 640)),
    ("CCTV Video (854x480)", (480, 854)),  # (height, width)
]

def format_mb(num_bytes: float) -> str:
    """Format bytes into MB."""
    return f"{num_bytes / (1024 * 1024):.2f} MB"

def get_process_ram_mb() -> float:
    """Get current resident set size (RSS) memory of the Python process."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

def main():
    print("=" * 65)
    print("      YOLO11s RAM USAGE & COMPUTE BENCHMARK TOOL")
    print("=" * 65)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}")

    # 1. HARDWARE ENVIRONMENT
    print("\n[1] HARDWARE & RUNTIME ENVIRONMENT:")
    print(f"  * Python Version     : {sys.version.split()[0]}")
    print(f"  * PyTorch Version    : {torch.__version__}")
    print(f"  * CUDA Available     : {torch.cuda.is_available()}")

    total_sys_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    available_sys_ram_gb = psutil.virtual_memory().available / (1024 ** 3)
    print(f"  * Total System RAM   : {total_sys_ram_gb:.2f} GB (Available: {available_sys_ram_gb:.2f} GB)")

    is_cuda = torch.cuda.is_available() and DEVICE != "cpu"
    if is_cuda:
        gpu_name = torch.cuda.get_device_name(DEVICE)
        gpu_vram_total_mb = torch.cuda.get_device_properties(DEVICE).total_memory / (1024 * 1024)
        print(f"  * Active GPU Device  : [{DEVICE}] {gpu_name}")
        print(f"  * Total GPU VRAM     : {gpu_vram_total_mb:.1f} MB ({gpu_vram_total_mb / 1024:.2f} GB)")
    else:
        print("  * Active Compute     : CPU only")

    # 2. MEASURE BASELINE MEMORY (BEFORE LOADING MODEL)
    ram_before_load = get_process_ram_mb()
    if is_cuda:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        vram_alloc_before = torch.cuda.memory_allocated(DEVICE) / (1024 * 1024)
        vram_reserved_before = torch.cuda.memory_reserved(DEVICE) / (1024 * 1024)

    # 3. LOAD MODEL & GATHER ARCHITECTURE COMPUTE STATS
    print("\n[2] LOADING MODEL & ARCHITECTURE COMPUTE SPECS:")
    model_size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    print(f"  * Model File Path    : {MODEL_PATH}")
    print(f"  * Model Disk Size    : {model_size_mb:.2f} MB")

    t_load_start = time.perf_counter()
    model = YOLO(str(MODEL_PATH))
    t_load_end = time.perf_counter()

    # Model architecture stats via PyTorch and Ultralytics
    pytorch_model = model.model
    total_params = sum(p.numel() for p in pytorch_model.parameters())
    trainable_params = sum(p.numel() for p in pytorch_model.parameters() if p.requires_grad)

    print(f"  * Model Load Time    : {(t_load_end - t_load_start) * 1000:.2f} ms")
    print(f"  * Total Parameters   : {total_params:,} ({total_params / 1e6:.2f} Million)")
    print(f"  * Trainable Params   : {trainable_params:,}")

    # Theoretical GFLOPs at 640x640 (standard input)
    try:
        from ultralytics.utils.torch_utils import get_flops
        flops = get_flops(pytorch_model, imgsz=640)
        print(f"  * Compute Complexity : {flops:.2f} GFLOPs (@ 640x640 resolution)")
    except Exception:
        print("  * Compute Complexity : ~21.8 GFLOPs (@ 640x640 resolution)")

    # 4. MEMORY FOOTPRINT AFTER LOAD
    ram_after_load = get_process_ram_mb()
    ram_delta_load = ram_after_load - ram_before_load

    print("\n[3] MEMORY FOOTPRINT (STATIC / POST-LOAD):")
    print(f"  * System RAM (Process Total) : {ram_after_load:.2f} MB")
    print(f"  * System RAM Delta (Model)   : +{ram_delta_load:.2f} MB")

    if is_cuda:
        vram_alloc_after = torch.cuda.memory_allocated(DEVICE) / (1024 * 1024)
        vram_reserved_after = torch.cuda.memory_reserved(DEVICE) / (1024 * 1024)
        print(f"  * GPU VRAM Allocated         : {vram_alloc_after:.2f} MB (Delta: +{vram_alloc_after - vram_alloc_before:.2f} MB)")
        print(f"  * GPU VRAM Reserved          : {vram_reserved_after:.2f} MB")

    # 5. BENCHMARK INFERENCE & ACTIVE RUNTIME COMPUTE
    print("\n[4] RUNTIME COMPUTE BENCHMARK & PEAK MEMORY:")

    for label, shape in RESOLUTIONS:
        h, w = shape
        dummy_input = np.zeros((h, w, 3), dtype=np.uint8)

        # Reset peak stats before benchmarking this resolution
        if is_cuda:
            torch.cuda.reset_peak_memory_stats(DEVICE)

        # Warmup
        for _ in range(WARMUP_ITERATIONS):
            _ = model.predict(dummy_input, device=DEVICE, verbose=False)

        # Timed inference
        latencies = []
        preprocess_times = []
        inference_times = []
        postprocess_times = []

        for _ in range(BENCHMARK_ITERATIONS):
            if is_cuda:
                torch.cuda.synchronize()

            t0 = time.perf_counter()
            results = model.predict(dummy_input, device=DEVICE, verbose=False)

            if is_cuda:
                torch.cuda.synchronize()
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000)

            # Extract internal speed breakdown (in ms)
            speed = results[0].speed
            preprocess_times.append(speed.get("preprocess", 0.0))
            inference_times.append(speed.get("inference", 0.0))
            postprocess_times.append(speed.get("postprocess", 0.0))

        mean_lat = np.mean(latencies)
        p50_lat = np.median(latencies)
        p95_lat = np.percentile(latencies, 95)
        min_lat = np.min(latencies)
        max_lat = np.max(latencies)
        fps = 1000.0 / mean_lat if mean_lat > 0 else 0

        mean_prep = np.mean(preprocess_times)
        mean_inf = np.mean(inference_times)
        mean_post = np.mean(postprocess_times)

        print(f"\n  -- Resolution: {label} [{w}x{h}] --")
        print(f"     Iterations Tested : {BENCHMARK_ITERATIONS} passes")
        print(f"     Average Latency   : {mean_lat:.2f} ms per frame")
        print(f"     Median (P50)      : {p50_lat:.2f} ms")
        print(f"     95th Percentile   : {p95_lat:.2f} ms")
        print(f"     Min / Max Latency : {min_lat:.2f} ms / {max_lat:.2f} ms")
        print(f"     Throughput (FPS)  : {fps:.1f} FPS")
        print("     Timing Breakdown  :")
        print(f"       * Preprocess    : {mean_prep:.2f} ms")
        print(f"       * Pure Forward  : {mean_inf:.2f} ms")
        print(f"       * Postprocess   : {mean_post:.2f} ms (NMS)")

        if is_cuda:
            vram_peak_alloc = torch.cuda.max_memory_allocated(DEVICE) / (1024 * 1024)
            vram_peak_reserved = torch.cuda.max_memory_reserved(DEVICE) / (1024 * 1024)
            print("     Memory Usage During Inference:")
            print(f"       * Peak VRAM Allocated : {vram_peak_alloc:.2f} MB")
            print(f"       * Peak VRAM Reserved  : {vram_peak_reserved:.2f} MB")
            print(f"       * VRAM % of Total GPU : {(vram_peak_reserved / gpu_vram_total_mb) * 100:.2f}%")

    # 6. DEPLOYMENT & CONCURRENCY ESTIMATE
    if is_cuda:
        print("\n[5] SYSTEM CAPACITY & CONCURRENCY ESTIMATE:")
        # Estimating headroom for 30 FPS cameras
        # If 1 frame takes ~11ms, in 1000ms GPU can process ~90 frames = ~3 full 30fps cameras serialized,
        # or dozens if processing at 5-10 FPS sample rate.
        fps_at_video_res = 1000.0 / mean_lat
        cams_at_30fps = int(fps_at_video_res // 30)
        cams_at_10fps = int(fps_at_video_res // 10)
        vram_per_model_mb = vram_peak_reserved
        max_instances_by_vram = int(gpu_vram_total_mb // max(vram_per_model_mb, 1))

        print(f"  * Real-Time 30 FPS Streams Supported (100% GPU saturation) : ~{cams_at_30fps} camera streams")
        print(f"  * Sampled 10 FPS Streams Supported (Standard CCTV)       : ~{cams_at_10fps} camera streams")
        print(f"  * Max Model Instances Supported by Available VRAM         : ~{max_instances_by_vram} instances")

    print("\n" + "=" * 65)
    print("                    BENCHMARK COMPLETE")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()

