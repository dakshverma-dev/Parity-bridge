"""Saved-run comparison engine."""
from __future__ import annotations

def _check_shots_match(left, right):
    return left.get("shot_digest") == right.get("shot_digest")
