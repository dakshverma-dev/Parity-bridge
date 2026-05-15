"""Benchmark harness: logical error rate, throughput and latency percentiles."""
from __future__ import annotations
import torch

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

def resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device

def ordered_decoders(decoders_dict, rep_idx: int):
    items = list(decoders_dict.items())
    if rep_idx % 2 == 1:
        items = list(reversed(items))
    return items
