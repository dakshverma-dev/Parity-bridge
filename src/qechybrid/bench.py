"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations

PROFILES = {
    "quick": dict(
        surface=dict(ds=[5, 7], ps=[0.002, 0.004], shots=20000, train=200000, val=50000, epochs=6, lat=500),
        qldpc=dict(codes=["bb72"], ps=[0.02, 0.04], shots=1000, lat=200),
    ),
    "full": dict(
        surface=dict(ds=[5, 7, 9, 13], ps=[0.001, 0.002, 0.004], shots=200000, train=400000, val=100000, epochs=8, lat=2000),
        qldpc=dict(codes=["bb72", "bb144"], ps=[0.02, 0.04, 0.06], shots=20000, lat=1000),
    ),
}

def run_profile(name="quick", only=None):
    prof = PROFILES[name]
    families = [only] if only else ["surface", "qldpc"]
    return {f: prof[f] for f in families if f in prof}
