"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations
import hashlib

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
