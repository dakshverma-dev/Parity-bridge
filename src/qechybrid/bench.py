"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import numpy as np
import time

def _measure_throughput(decoder, data, reps=5):
    batch_times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        decoder.decode_batch(data)
        batch_times.append(time.perf_counter() - t0)
    throughputs = [len(data) / t for t in batch_times]
    return {
        "raw_batch_times_s": batch_times,
        "throughput_shots_per_s": float(np.median(throughputs)),
    }
