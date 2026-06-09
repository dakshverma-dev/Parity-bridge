"""Release report contract for the ParityBridge report viewer.

Standard library only, so the viewer image does not need the research stack.
The adapter reads the CSV written by ``scripts/run_benchmarks.py --only surface``
and keeps the harness's column names, definitions and units unchanged.
"""
from __future__ import annotations

import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SOURCE_KINDS = ("measured", "fixture", "historical")

# Exact header of surface.csv under benchmark_protocol "median-paired-v2".
# A change here means the harness changed: the adapter refuses to guess.
SURFACE_COLUMNS = (
    "code", "d", "rounds", "p", "decoder", "device", "shots", "errors", "ler", "ler_lo", "ler_hi",
    "throughput_sps", "throughput_reps", "throughput_min_sps", "throughput_max_sps",
    "throughput_q25_sps", "throughput_q75_sps", "throughput_times_s", "paired_baseline_times_s",
    "paired_ratio_median", "paired_ratio_min", "paired_ratio_max", "paired_ratio_q25",
    "paired_ratio_q75", "lat_p50_us", "lat_p95_us", "lat_p99_us", "lat_b256_ms", "accept_rate",
    "syndrome_weight_kept", "t_stage1_s", "t_global_s", "extra",
)
EXPECTED_PROTOCOL = "median-paired-v2"

# Columns published in the report, with the harness's own definitions and units.
METRIC_FIELDS = {
    "code": ("", "code family"),
    "d": ("", "code distance"),
    "rounds": ("", "syndrome-extraction rounds"),
    "p": ("", "physical error rate"),
    "decoder": ("", "decoder under test"),
    "device": ("", "execution device"),
    "shots": ("shots", "decoded shots"),
    "errors": ("shots", "logical errors on those shots"),
    "ler": ("", "logical error rate = errors / shots"),
    "ler_lo": ("", "Wilson 95% interval, lower bound"),
    "ler_hi": ("", "Wilson 95% interval, upper bound"),
    "throughput_sps": ("shots/s", "median batch throughput over throughput_reps repetitions"),
    "throughput_reps": ("", "throughput repetitions"),
    "lat_p50_us": ("us", "single-shot latency, 50th percentile"),
    "lat_p95_us": ("us", "single-shot latency, 95th percentile"),
    "lat_p99_us": ("us", "single-shot latency, 99th percentile"),
}
INT_FIELDS = {"d", "rounds", "shots", "errors", "throughput_reps"}
STR_FIELDS = {"code", "decoder", "device"}

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_RAW_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.csv$")
MAX_RAW_BYTES = 1_000_000


class ReportError(ValueError):
    """The report or its inputs do not satisfy the contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _need(obj: dict, key: str, kind, where: str):
    if not isinstance(obj, dict) or key not in obj:
        raise ReportError(f"{where}.{key} is missing")
    val = obj[key]
    if kind in (int, (int, float)) and type(val) is bool:
        raise ReportError(f"{where}.{key} must be numeric")
    if not isinstance(val, kind):
        raise ReportError(f"{where}.{key} must be {getattr(kind, '__name__', kind)}")
    return val


def validate_report(report: dict) -> dict:
    """Return ``report`` unchanged if it satisfies schema version 1, else raise ReportError."""
    if not isinstance(report, dict):
        raise ReportError("report must be a JSON object")
    expected = {"schemaVersion", "reportId", "commitSha", "generatedAt", "sourceKind", "command",
                "environment", "tests", "benchmark", "provenance"}
    extra = set(report) - expected
    if extra:
        raise ReportError(f"unexpected top-level fields: {sorted(extra)}")
    if _need(report, "schemaVersion", int, "report") != SCHEMA_VERSION:
        raise ReportError(f"schemaVersion must be {SCHEMA_VERSION}")
    if not _need(report, "reportId", str, "report").strip():
        raise ReportError("reportId must be nonempty")
    if not _SHA_RE.match(_need(report, "commitSha", str, "report")):
        raise ReportError("commitSha must be a 40-character lowercase hex SHA")
    if not _TS_RE.match(_need(report, "generatedAt", str, "report")):
        raise ReportError("generatedAt must be a UTC timestamp like 2026-10-21T14:00:00Z")
    if _need(report, "sourceKind", str, "report") not in SOURCE_KINDS:
        raise ReportError(f"sourceKind must be one of {SOURCE_KINDS}")
    if not _need(report, "command", str, "report").strip():
        raise ReportError("command must be nonempty")

    env = _need(report, "environment", dict, "report")
    for k in ("python", "device", "platform"):
        _need(env, k, str, "environment")

    tests = _need(report, "tests", dict, "report")
    for k in ("passed", "failed", "skipped"):
        if _need(tests, k, int, "tests") < 0:
            raise ReportError(f"tests.{k} must be >= 0")

    bench = _need(report, "benchmark", dict, "report")
    if _need(bench, "status", str, "benchmark") not in ("passed", "failed"):
        raise ReportError("benchmark.status must be passed or failed")
    _need(bench, "conditions", dict, "benchmark")
    metrics = _need(bench, "metrics", list, "benchmark")
    for i, row in enumerate(metrics):
        where = f"benchmark.metrics[{i}]"
        if not isinstance(row, dict) or set(row) != set(METRIC_FIELDS):
            raise ReportError(f"{where} must have exactly the fields {sorted(METRIC_FIELDS)}")
        for k in METRIC_FIELDS:
            kind = str if k in STR_FIELDS else int if k in INT_FIELDS else (int, float)
            value = _need(row, k, kind, where)
            if isinstance(value, float) and not math.isfinite(value):
                raise ReportError(f"{where}.{k} must be finite")
    raw = _need(bench, "rawFile", str, "benchmark")
    if not _RAW_NAME_RE.match(raw):
        raise ReportError("benchmark.rawFile must be a bare .csv file name")

    prov = _need(report, "provenance", dict, "report")
    _need(prov, "baselineUrl", str, "provenance")
    paths = _need(prov, "sourcePaths", list, "provenance")
    if not all(isinstance(p, str) for p in paths):
        raise ReportError("provenance.sourcePaths must be strings")
    _need(prov, "pipelineUrl", str, "provenance")
    return report


def validate_build(build: dict, report: dict) -> dict:
    """``release_build.json`` must name the same commit and report as the bundled report."""
    if not isinstance(build, dict):
        raise ReportError("build metadata must be a JSON object")
    if build.get("commitSha") != report["commitSha"]:
        raise ReportError("release_build.json commitSha does not match the report")
    if build.get("reportId") != report["reportId"]:
        raise ReportError("release_build.json reportId does not match the report")
    return build


def parse_junit(path: str | Path) -> dict:
    """Test counts from a pytest JUnit XML file."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites:
        raise ReportError(f"{path}: no testsuite element")
    total = failed = skipped = 0
    for s in suites:
        total += int(s.get("tests", 0))
        failed += int(s.get("failures", 0)) + int(s.get("errors", 0))
        skipped += int(s.get("skipped", 0))
    return {"passed": total - failed - skipped, "failed": failed, "skipped": skipped}


def _num(field: str, text: str):
    if field in STR_FIELDS:
        return text
    if field in INT_FIELDS:
        return int(text)
    return float(text)


def benchmark_csv_rows(stream, columns: tuple[str, ...], label) -> list[dict]:
    reader = csv.DictReader(stream, strict=True)
    header = tuple(reader.fieldnames or ())
    if header != columns:
        missing = [c for c in columns if c not in header]
        added = [c for c in header if c not in columns]
        raise ReportError(f"{label}: unexpected columns (missing={missing}, added={added})")
    rows = list(reader)
    if not rows:
        raise ReportError(f"{label}: no benchmark rows")
    if any(None in row or None in row.values() for row in rows):
        raise ReportError(f"{label}: malformed benchmark row")
    return rows


def read_surface_csv(path: str | Path) -> list[dict]:
    """Rows of a surface.csv, reduced to METRIC_FIELDS. Raises on any header change."""
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: _num(k, row[k]) for k in METRIC_FIELDS}
                for row in benchmark_csv_rows(f, SURFACE_COLUMNS, path)]


def conditions_from_meta(meta: dict) -> dict:
    """Measurement conditions shown beside the metrics, taken from the harness's meta.json."""
    if meta.get("benchmark_protocol") != EXPECTED_PROTOCOL:
        raise ReportError(f"meta.json benchmark_protocol must be {EXPECTED_PROTOCOL!r}")
    surface = meta.get("config", {}).get("surface", {})
    return {
        "profile": meta.get("profile"),
        "benchmarkProtocol": meta["benchmark_protocol"],
        "decoderOrder": meta.get("decoder_order"),
        "throughputReps": meta.get("throughput_reps"),
        "surfaceModes": surface.get("modes"),
        "distances": surface.get("ds"),
        "physicalErrorRates": surface.get("ps"),
        "shotsPerPoint": surface.get("shots"),
        "latencySamples": surface.get("lat"),
        "noiseModel": ("stim surface_code:rotated_memory_z, rounds = d, uniform circuit-level noise p "
                       "(src/qechybrid/data.py surface_circuit)"),
        "cpuCount": meta.get("cpu_count"),
        "torchThreads": meta.get("torch_num_threads"),
        "versions": {k: meta.get(k) for k in ("torch", "stim", "pymatching", "ldpc")},
        "harnessCommit": meta.get("git_commit"),
        "harnessDirty": meta.get("git_dirty"),
        "harnessTimestamp": meta.get("timestamp"),
        "sourceSha256": meta.get("source_sha256"),
    }


def build_report(*, results_dir: str | Path, junit: str | Path, commit_sha: str, command: str,
                 source_kind: str, baseline_url: str, pipeline_url: str = "",
                 results_label: str | None = None, report_id: str | None = None,
                 generated_at: str | None = None) -> dict:
    """Assemble and validate a report from one benchmark output folder and one JUnit file.

    ``results_label`` is the repository-relative name of ``results_dir`` recorded in provenance.
    """
    results_dir = Path(results_dir)
    results_label = results_label or results_dir.as_posix()
    meta = json.loads((results_dir / "meta.json").read_text(encoding="utf-8"))
    harness = str(meta.get("git_commit") or "")
    if source_kind == "measured" and (not harness or not commit_sha.startswith(harness)):
        raise ReportError(f"benchmark ran at commit {harness!r}, not {commit_sha}")
    generated_at = generated_at or utc_now()
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "reportId": report_id or f"{commit_sha[:12]}-{generated_at.replace(':', '').replace('-', '')}",
        "commitSha": commit_sha,
        "generatedAt": generated_at,
        "sourceKind": source_kind,
        "command": command,
        "environment": {"python": str(meta.get("python")), "device": str(meta.get("device")),
                        "platform": str(meta.get("platform"))},
        "tests": parse_junit(junit),
        "benchmark": {
            "status": "passed",
            "conditions": conditions_from_meta(meta),
            "metrics": read_surface_csv(results_dir / "surface.csv"),
            "rawFile": "surface.csv",
        },
        "provenance": {
            "baselineUrl": baseline_url,
            "sourcePaths": ["scripts/run_benchmarks.py", "src/qechybrid/bench.py",
                            f"{results_label}/surface.csv", f"{results_label}/meta.json"],
            "pipelineUrl": pipeline_url,
        },
    }
    return validate_report(report)


def load_bundle(data_dir: str | Path) -> tuple[dict, dict, Path]:
    """Load and cross-check the bundled report, build metadata and raw file."""
    data_dir = Path(data_dir)
    try:
        report = json.loads((data_dir / "release_report.json").read_text(encoding="utf-8"))
        build = json.loads((data_dir / "release_build.json").read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ReportError(f"missing {Path(e.filename).name}") from e
    except json.JSONDecodeError as e:
        raise ReportError(f"invalid JSON: {e}") from e
    validate_report(report)
    validate_build(build, report)
    raw = data_dir / report["benchmark"]["rawFile"]
    if not raw.is_file():
        raise ReportError(f"raw file {raw.name} is not bundled")
    if raw.stat().st_size > MAX_RAW_BYTES:
        raise ReportError(f"raw file {raw.name} exceeds {MAX_RAW_BYTES} bytes")
    return report, build, raw
