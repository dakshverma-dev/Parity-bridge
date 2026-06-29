"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

BUNDLE_SCHEMA_VERSION = "1.0.0"
FAMILIES = ("surface", "qldpc")
SOURCE_KINDS = ("measured", "fixture", "historical")

def validate_source(source: str):
    if source not in SOURCE_KINDS:
        raise ValueError(f"Unknown source kind {source}")
