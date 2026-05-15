"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import numpy as np

def _throughput_metrics(throughputs: list[float]) -> dict:
    arr = np.asarray(throughputs, dtype=np.float64)
    return {
        "throughput_median": float(np.median(arr)),
        "throughput_min": float(np.min(arr)),
        "throughput_max": float(np.max(arr)),
    }
