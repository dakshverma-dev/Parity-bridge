"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations

BUNDLE_SCHEMA_VERSION = "1.0.0"
FAMILIES = ("surface", "qldpc")
SOURCE_KINDS = ("measured", "fixture", "historical")

def _manifest_checks(manifest: dict):
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ValueError("Invalid schema version")
