"""Validation and assembly for version-one ParityBridge release reports."""
from __future__ import annotations

SCHEMA_VERSION = "1.0.0"

class ReportError(ValueError):
    pass

def validate_report(report: dict) -> dict:
    if report.get("schemaVersion") != SCHEMA_VERSION:
        raise ReportError(f"unsupported schemaVersion {report.get('schemaVersion')!r}; expected {SCHEMA_VERSION!r}")
    return report

def validate_build(build: dict) -> dict:
    for key in ("commitSha", "reportId", "builtAt"):
        if key not in build:
            raise ReportError(f"build missing required field {key!r}")
    return build
