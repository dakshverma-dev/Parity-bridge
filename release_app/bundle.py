"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations
import shutil
from pathlib import Path

def copy_csv_exact(src: Path, dst: Path):
    shutil.copyfile(src, dst)
