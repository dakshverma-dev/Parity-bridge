"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import numpy as np
import time
from .timing import percentiles_us

def _latency(decode_fn, single_shots, n_samples=100) -> dict:
    times = []
    subset = single_shots[:n_samples]
    for s in subset:
        t0 = time.perf_counter()
        decode_fn(s[None, :])
        times.append(time.perf_counter() - t0)
    return percentiles_us(times)
