"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

def _check_shots(row, cfg):
    if int(row["shots"]) != int(cfg["shots"]):
        raise ValueError("Mismatched shots count")
