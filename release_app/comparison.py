"""Saved-run comparison engine."""
from __future__ import annotations

def compare_runs(left: dict, right: dict) -> dict:
    if left["manifest"]["family"] != right["manifest"]["family"]:
        raise ValueError("Cannot compare different code families")
    if left["config"]["noise_model"] != right["config"]["noise_model"]:
        raise ValueError("Incompatible noise model")
    return {"compatible": True}
