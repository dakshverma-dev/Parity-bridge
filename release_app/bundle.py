"""Versioned, immutable benchmark bundles for the local workbench."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .report import (EXPECTED_PROTOCOL, INT_FIELDS, SOURCE_KINDS, STR_FIELDS, SURFACE_COLUMNS,
                     ReportError, benchmark_csv_rows, utc_now)

SCHEMA_VERSION = 1
MANIFEST = "manifest.json"
FAMILIES = {"surface": "stim-rotated-memory-z-circuit-level", "qldpc": "bb-code-capacity-bit-flip"}
QLDPC_CODES = {"bb72": "BB[[72,12,6]]", "bb144": "BB[[144,12,12]]"}
QLDPC_COLUMNS = SURFACE_COLUMNS[:SURFACE_COLUMNS.index("syndrome_weight_kept")] + ("extra",)
DEPENDENCIES = ("torch", "numpy", "scipy", "pandas", "stim", "pymatching", "ldpc")
HARDWARE = ("device", "platform", "architecture", "cpu_model", "cpu_count", "gpu", "cuda", "nvidia_driver")
TIMING_ENV = ("torch_num_threads", "torch_num_interop_threads", "timing_environment")
REPETITIONS = {"throughput_times_s", "paired_baseline_times_s"}
OPTIONAL_METRICS = {"accept_rate", "lat_b256_ms"}
LIMIT = 32 * 1024 * 1024
_RUN_ID = re.compile(r"[a-z0-9](?:[a-z0-9_-]{0,63})")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10))}
_HEX = re.compile(r"[0-9a-f]+")


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id) or run_id in _WINDOWS_RESERVED:
        raise ReportError("run ID must be a safe name of up to 64 lowercase letters, digits, hyphens or underscores")
    return run_id


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value, lengths: tuple[int, ...]) -> bool:
    return isinstance(value, str) and len(value) in lengths and bool(_HEX.fullmatch(value))


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and all(ord(c) >= 32 for c in value)


def _number(value) -> bool:
    return type(value) in (int, float) and -math.inf < value < math.inf


def _integer(value, minimum=1) -> bool:
    return type(value) is int and value >= minimum


def _file(directory: Path, name: str) -> bytes:
    # Filenames are fixed by the schema. Resolve again to reject junctions and symlinks.
    path = directory / name
    if path.is_symlink() or path.resolve() != directory.resolve() / name or not path.is_file():
        raise ReportError(f"missing or unsafe artifact {name}")
    with path.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ReportError(f"artifact {name} exceeds {LIMIT} bytes")
    return data


def _json(data: bytes):
    def reject_constant(value):
        raise ReportError(f"non-finite JSON value {value}")

    def object_pairs(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ReportError("duplicate JSON key")
        return result

    value = json.loads(data, parse_constant=reject_constant, object_pairs_hook=object_pairs)
    # The decoder also accepts exponent overflow as float infinity.
    json.dumps(value, allow_nan=False)
    return value


def _utc(value) -> bool:
    if not _text(value):
        return False
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return date.utcoffset() is not None and date.utcoffset().total_seconds() == 0


def _manifest_checks(manifest: dict) -> set[str]:
    required = {"schema_version", "run_id", "source_kind", "created_at_utc", "code_family",
                "noise_model", "benchmark_protocol", "harness_sha", "command", "artifacts"}
    if not isinstance(manifest, dict) or manifest.keys() != required:
        raise ReportError("unexpected manifest fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise ReportError("unsupported bundle schema version")
    validate_run_id(manifest["run_id"])
    family, source = manifest["code_family"], manifest["source_kind"]
    if family not in FAMILIES or source not in SOURCE_KINDS:
        raise ReportError("invalid code family or source kind")
    if manifest["noise_model"] != FAMILIES[family] or manifest["benchmark_protocol"] != EXPECTED_PROTOCOL:
        raise ReportError("unsupported noise model or benchmark protocol")
    if not _utc(manifest["created_at_utc"]) or not _text(manifest["command"]):
        raise ReportError("invalid bundle creation time or command")
    sha = manifest["harness_sha"]
    if sha is not None and not _hex(sha, tuple(range(7, 41))):
        raise ReportError("invalid harness SHA")
    artifacts = manifest["artifacts"]
    names = {"meta.json", f"{family}.csv"}
    if source == "measured":
        names.add("shots.json")
        if not _hex(sha, (40,)):
            raise ReportError("a measured bundle requires the full harness SHA")
    if not isinstance(artifacts, dict) or artifacts.keys() != names:
        raise ReportError("unexpected or unsafe artifact names")
    if any(not _hex(digest, (64,)) for digest in artifacts.values()):
        raise ReportError("invalid artifact SHA-256")
    return names


def _config(meta, family, measured):
    which = meta.get("which")
    if not isinstance(which, list) or family not in which or any(f not in FAMILIES for f in which):
        raise ReportError("invalid benchmark families in meta.json")
    config = meta.get("config")
    if not isinstance(config, dict) or not isinstance(config.get(family), dict):
        raise ReportError("missing benchmark configuration")
    cfg = config[family]
    for name in ("shots", "lat", "reps"):
        if not _integer(cfg.get(name), 3 if name == "reps" else 1):
            raise ReportError(f"invalid {family} configuration field {name}")
    if cfg["reps"] != meta.get("throughput_reps"):
        raise ReportError("inconsistent throughput repetition count")
    ps = cfg.get("ps")
    if (not isinstance(ps, list) or not ps or not all(_number(p) and 0 <= p <= 1 for p in ps)
            or len(set(ps)) != len(ps)):
        raise ReportError("invalid physical error rate grid")
    if family == "surface":
        ds = cfg.get("ds")
        if (not isinstance(ds, list) or not ds or not all(_integer(d, 2) for d in ds)
                or len(set(ds)) != len(ds)):
            raise ReportError("invalid distance grid")
        modes = cfg.get("modes", ["none", "zero", "local", "nn"])
        if not isinstance(modes, list) or not modes or any(m not in ("none", "zero", "local", "nn") for m in modes):
            raise ReportError("invalid surface decoder modes")
        if "nn" in modes and any(not _integer(cfg.get(name)) for name in ("train", "val", "epochs")):
            raise ReportError("invalid surface training settings")
        points = {("surface", d, d, p) for d in ds for p in ps}
    else:
        codes = cfg.get("codes")
        if (not isinstance(codes, list) or not codes
                or any(not isinstance(c, str) or c not in QLDPC_CODES for c in codes)
                or len(set(codes)) != len(codes)):
            raise ReportError("invalid bivariate-bicycle code grid")
        points = {(QLDPC_CODES[c], 0, 0, p) for c in codes for p in ps}
    if measured and which != [family]:
        raise ReportError("measured evidence must capture one code family")
    return cfg, points


def _metadata(manifest, meta):
    family = manifest["code_family"]
    measured = manifest["source_kind"] == "measured"
    if not isinstance(meta, dict) or meta.get("benchmark_protocol") != manifest["benchmark_protocol"]:
        raise ReportError("invalid meta.json benchmark protocol")
    if meta.get("profile") not in ("quick", "full") or not _text(meta.get("decoder_order")):
        raise ReportError("invalid benchmark profile or decoder order")
    for name in ("python", "platform", "device"):
        if not _text(meta.get(name)):
            raise ReportError(f"missing or invalid metadata field {name}")
    for name in ("cpu_count", "torch_num_threads", "torch_num_interop_threads"):
        if (measured or name in meta) and not _integer(meta.get(name)):
            raise ReportError(f"missing or invalid metadata field {name}")
    if manifest["harness_sha"] != (meta.get("harness_commit") or meta.get("git_commit") or None):
        raise ReportError("harness SHA does not match meta.json")
    if measured:
        if meta.get("run_id") != manifest["run_id"] or not _utc(meta.get("started_at_utc")):
            raise ReportError("invalid measured run identity or timestamp")
        if meta["device"] != "cpu" or not _integer(meta.get("sampling_seed"), 0):
            raise ReportError("measured smoke evidence requires a CPU device and a sampling seed")
        # A CUDA-capable build can still report its runtime version while measuring on CPU.
        if (any(key not in meta for key in HARDWARE) or meta["gpu"] is not None
                or meta["nvidia_driver"] is not None or (meta["cuda"] is not None and not _text(meta["cuda"]))):
            raise ReportError("invalid CPU hardware metadata")
        if type(meta.get("git_dirty")) is not bool or not _hex(meta.get("source_sha256"), (64,)):
            raise ReportError("invalid harness source fingerprint")
        if not _text(meta.get("architecture")) or not _text(meta.get("cpu_model")):
            raise ReportError("missing CPU hardware identity")
        dependencies = meta.get("dependencies")
        if (not isinstance(dependencies, dict) or dependencies.keys() != set(DEPENDENCIES)
                or not all(_text(v) for v in dependencies.values())):
            raise ReportError("missing dependency versions")
        timing = meta.get("timing_environment")
        if (not isinstance(timing, dict)
                or any(v is not None and not _text(v) for v in timing.values())
                or timing.keys() != {"OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_PROC_BIND"}):
            raise ReportError("invalid timing environment")
    return _config(meta, family, measured)


def point(row):
    return tuple(row[k] for k in ("code", "d", "rounds", "p"))


def _rows(data, family, allowed_points, cfg, measured):
    columns = SURFACE_COLUMNS if family == "surface" else QLDPC_COLUMNS
    raw = benchmark_csv_rows(io.StringIO(data.decode("utf-8"), newline=""), columns, f"{family}.csv")
    rows = {}
    for entry in raw:
        row = {}
        for key, value in entry.items():
            if key in STR_FIELDS or key == "extra":
                row[key] = value
            elif key in REPETITIONS:
                times = _json(value.encode())
                if (not isinstance(times, list) or len(times) != cfg["reps"]
                        or not all(_number(t) and t > 0 for t in times)):
                    raise ReportError(f"invalid repetitions in {key}")
                row[key] = times
            elif key in OPTIONAL_METRICS and value == "":
                row[key] = None
            else:
                number = int(value) if key in INT_FIELDS else float(value)
                if not _number(number) or number < 0:
                    raise ReportError(f"{key} must be finite and nonnegative")
                row[key] = number
        if not _text(row["decoder"]) or not _text(row["device"]) or (measured and row["device"] != "cpu"):
            raise ReportError("invalid benchmark decoder or timing device")
        identity = (*point(row), row["decoder"])
        if identity in rows or point(row) not in allowed_points:
            raise ReportError("duplicate or unexpected parameter point and decoder")
        if row["shots"] != cfg["shots"] or row["throughput_reps"] != cfg["reps"]:
            raise ReportError("shot or repetition counts differ from the configuration")
        if (row["errors"] > row["shots"] or row["ler"] != row["errors"] / row["shots"]
                or not row["ler_lo"] <= row["ler"] <= row["ler_hi"] <= 1):
            raise ReportError("inconsistent logical-error counts or interval")
        if row["throughput_sps"] <= 0 or not 0 < row["lat_p50_us"] <= row["lat_p95_us"] <= row["lat_p99_us"]:
            raise ReportError("invalid throughput or latency")
        if row["accept_rate"] is not None and row["accept_rate"] > 1:
            raise ReportError("acceptance rate exceeds one")
        rows[identity] = row
    if {point(row) for row in rows.values()} != allowed_points:
        raise ReportError("benchmark is missing one or more configured parameter points")
    if measured:
        expected_decoders = {"ldpc BP+OSD (CPU)", "GPU min-sum BP + OSD fallback"}
        if family == "surface":
            expected_decoders = {"pymatching (CPU)"}
            modes = cfg.get("modes", ("none", "zero", "local", "nn"))
            if "zero" in modes:
                expected_decoders.add("zero-syndrome shortcut + pymatching")
            if "local" in modes:
                expected_decoders.update(("GPU local pre-decoder (conservative, r=2) + pymatching",
                                          "GPU local pre-decoder (fast, r=1) + pymatching"))
            if "nn" in modes:
                expected_decoders.add("AI gate (MLP, strict) + pymatching")
        if rows.keys() != {(*p, decoder) for p in allowed_points for decoder in expected_decoders}:
            raise ReportError("measured benchmark is missing one or more configured decoder rows")
    return rows


def _attach_shots(data, rows):
    entries = _json(data)
    if not isinstance(entries, list) or len(entries) != len(rows):
        raise ReportError("shot evidence must contain one entry per metric row")
    seen = set()
    digests = {}
    for entry in entries:
        names = {"code", "d", "rounds", "p", "decoder", "shot_sha256", "logical_failures", "diagnostic_cpu_fallback_s"}
        if not isinstance(entry, dict) or entry.keys() != names:
            raise ReportError("invalid shot evidence fields")
        identity = (*point(entry), entry["decoder"])
        if identity in seen or identity not in rows:
            raise ReportError("duplicate or unknown shot evidence row")
        seen.add(identity)
        row = rows[identity]
        if not _integer(entry["d"], 0) or not _integer(entry["rounds"], 0) or not _number(entry["p"]):
            raise ReportError("invalid shot evidence parameter point")
        digest, failures, fallback = (entry[k] for k in ("shot_sha256", "logical_failures", "diagnostic_cpu_fallback_s"))
        if not _hex(digest, (64,)) or digest != digests.setdefault(point(row), digest):
            raise ReportError("mismatched ordered shot fingerprints")
        if (not isinstance(failures, str) or len(failures) != row["shots"]
                or set(failures) - {"0", "1"} or failures.count("1") != row["errors"]):
            raise ReportError("per-shot failures do not match logical error and shot counts")
        if fallback is not None and (not _number(fallback) or fallback < 0 or row["code"] == "surface"):
            raise ReportError("invalid CPU fallback timing")
        if (row["decoder"] == "GPU min-sum BP + OSD fallback") != (fallback is not None):
            raise ReportError("CPU fallback timing must be present for the hybrid qLDPC decoder")
        row.update(shot_sha256=digest, logical_failures=failures, diagnostic_cpu_fallback_s=fallback)


def load_benchmark_bundle(directory: Path) -> dict:
    """Validate and read the same bytes used for hashing. No paths come from requests."""
    directory = Path(directory)
    try:
        manifest = _json(_file(directory, MANIFEST))
        names = _manifest_checks(manifest)
        artifacts = {name: _file(directory, name) for name in sorted(names)}
        for name, data in artifacts.items():
            if _digest(data) != manifest["artifacts"][name]:
                raise ReportError(f"hash mismatch for {name}")
        meta = _json(artifacts["meta.json"])
        family = manifest["code_family"]
        cfg, allowed_points = _metadata(manifest, meta)
        rows = _rows(artifacts[f"{family}.csv"], family, allowed_points, cfg, manifest["source_kind"] == "measured")
        if "shots.json" in artifacts:
            _attach_shots(artifacts["shots.json"], rows)
        return {"manifest": manifest, "metadata": meta, "rows": list(rows.values())}
    except ReportError:
        raise
    except (OSError, ValueError, TypeError, csv.Error, RuntimeError) as exc:
        raise ReportError(f"malformed benchmark bundle: {exc}") from exc


def write_benchmark_bundle(root: Path, run_id: str, results: Path, *, family: str, source_kind: str, command: str) -> Path:
    """Publish one validated run by renaming a sibling directory on the same volume."""
    validate_run_id(run_id)
    if family not in FAMILIES or source_kind not in SOURCE_KINDS:
        raise ReportError("invalid code family or source kind")
    if not _text(command):
        raise ReportError("invalid benchmark command")
    root = Path(root)
    destination = root / run_id
    root.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise ReportError(f"bundle {run_id} already exists")
    names = ["meta.json", f"{family}.csv"]
    if source_kind == "measured":
        names.append("shots.json")
    with TemporaryDirectory(prefix=".staging-", dir=root) as staging:
        payload = Path(staging) / run_id
        payload.mkdir()
        artifacts = {name: _file(Path(results), name) for name in names}
        meta = _json(artifacts["meta.json"])
        if not isinstance(meta, dict):
            raise ReportError("meta.json must contain an object")
        manifest = {
            "schema_version": SCHEMA_VERSION, "run_id": run_id, "source_kind": source_kind,
            "created_at_utc": utc_now(), "code_family": family, "noise_model": FAMILIES[family],
            "benchmark_protocol": meta.get("benchmark_protocol"),
            "harness_sha": meta.get("harness_commit") or meta.get("git_commit") or None,
            "command": command, "artifacts": {name: _digest(data) for name, data in artifacts.items()},
        }
        for name, data in artifacts.items():
            (payload / name).write_bytes(data)
        (payload / MANIFEST).write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        load_benchmark_bundle(payload)
        # Once another publisher wins, its directory is nonempty and cannot be replaced.
        payload.rename(destination)
    return destination


def load_saved_run(root: Path, run_id: str) -> dict:
    validate_run_id(run_id)
    root = Path(root)
    directory = root / run_id
    if directory.is_symlink() or directory.resolve() != root.resolve() / run_id:
        raise ReportError("unsafe bundle directory")
    run = load_benchmark_bundle(directory)
    if run["manifest"]["run_id"] != run_id:
        raise ReportError("bundle run ID does not match its directory")
    return run
