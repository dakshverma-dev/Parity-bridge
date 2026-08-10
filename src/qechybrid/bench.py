"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import hashlib

def _shot_digest_surface(dets, obs) -> str:
    return hashlib.md5(dets.tobytes() + obs.tobytes()).hexdigest()
