"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

def _check_duplicates(rows):
    seen = set()
    for r in rows:
        key = (r.get("distance") or r.get("code"), r.get("p"), r.get("decoder"))
        if key in seen:
            raise ValueError(f"Duplicate row for {key}")
        seen.add(key)
