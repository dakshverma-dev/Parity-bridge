"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import numpy as np
import time

def _batch_latency_ms(decode_fn, data, batch_size=256, reps=10) -> float:
    chunk = data[:batch_size]
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        decode_fn(chunk)
        times.append(time.perf_counter() - t0)
    return float(np.median(times) * 1e3)
