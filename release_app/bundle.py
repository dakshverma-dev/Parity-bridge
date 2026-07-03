"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

def _check_grid(row: dict, grid: dict):
    if "p" in row and row["p"] not in grid.get("noise_rates", [row["p"]]):
        raise ValueError("row outside configured parameter grid")
