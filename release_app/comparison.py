"""Saved-run comparison engine."""
from __future__ import annotations

def _performance_reason(left, right):
    if left["metadata"].get("cpu_model") != right["metadata"].get("cpu_model"):
        return "CPU model mismatch prevents speed comparison"
    return None
