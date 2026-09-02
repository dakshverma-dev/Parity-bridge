"""Saved-run comparison engine."""
from __future__ import annotations

def _check_timing_device(left, right):
    return left.get("timing_device") == right.get("timing_device")
