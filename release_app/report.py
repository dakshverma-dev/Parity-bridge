"""Validation and assembly for version-one ParityBridge release reports."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

class ReportError(ValueError):
    pass

def parse_junit(junit_xml: Path) -> dict[str, int]:
    tree = ET.parse(junit_xml)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    tests = sum(int(s.attrib.get("tests", 0)) for s in suites)
    failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
    errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
    skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    failed = failures + errors
    passed = tests - failed - skipped
    return {"passed": passed, "failed": failed, "skipped": skipped, "total": tests}
