"""Saved-run comparison engine."""
from __future__ import annotations

def _speed_factor(left_tp: float, right_tp: float) -> float:
    return float(right_tp / left_tp) if left_tp > 0 else 0.0
