"""Saved-run comparison engine."""
from __future__ import annotations

def _latency_speed_factor(left_lat: float, right_lat: float) -> float:
    return float(left_lat / right_lat) if right_lat > 0 else 0.0
