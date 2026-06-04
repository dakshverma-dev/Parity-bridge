"""Validation and assembly for version-one ParityBridge release reports."""
from __future__ import annotations
import csv
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

class ReportError(ValueError):
    pass

def _num(val: str, name: str) -> int | float:
    try:
        f = float(val)
        return int(f) if f.is_integer() and "." not in val else f
    except ValueError:
        raise ReportError(f"field {name!r} is not numeric: {val!r}")

def read_surface_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
