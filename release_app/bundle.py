"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

BUNDLE_SCHEMA_VERSION = "1.0.0"
FAMILIES = ("surface", "qldpc")
SOURCE_KINDS = ("measured", "fixture", "historical")

def _metadata(meta: dict) -> dict:
    return {
        "cpu_model": meta.get("cpu_model", "unknown"),
        "torch_version": meta.get("torch_version", "unknown"),
        "stim_version": meta.get("stim_version", "unknown"),
    }
