"""Unified benchmark bundles for surface and qLDPC runs."""
from __future__ import annotations
import csv

def _rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
