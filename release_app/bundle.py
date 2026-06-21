"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

BUNDLE_SCHEMA_VERSION = "1.0.0"
FAMILIES = ("surface", "qldpc")
SOURCE_KINDS = ("measured", "fixture", "historical")

def _config(cfg: dict) -> dict:
    return {
        "seed": cfg.get("seed", 0),
        "distances": cfg.get("distances", []),
        "noise_rates": cfg.get("noise_rates", []),
    }
