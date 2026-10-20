import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from release_app.report import (METRIC_FIELDS, ReportError, build_report, load_bundle, parse_junit,
                                read_surface_csv, validate_report)

FIX = Path(__file__).parent / "fixtures"
SMOKE = FIX / "smoke"
ROOT = Path(__file__).resolve().parents[2]
# meta.json in the fixture was produced at this commit (git_commit = e9de2f3).
HARNESS_SHA = "e9de2f3ac645bf9ed0b6a50ad86c2e48ff193bdf"
OTHER_SHA = "0123456789abcdef0123456789abcdef01234567"


def make_report(**kw):
    args = dict(results_dir=SMOKE, junit=FIX / "junit.xml", commit_sha=HARNESS_SHA,
                command="python scripts/run_benchmarks.py --profile quick", source_kind="fixture",
                baseline_url="https://github.com/dakshverma-dev/ParityBridge",
                generated_at="2026-10-21T14:19:57Z")
    args.update(kw)
    return build_report(**args)


def write_bundle(tmp_path, report, build=None):
    (tmp_path / "release_report.json").write_text(json.dumps(report))
    build = build or {"commitSha": report["commitSha"], "reportId": report["reportId"]}
    (tmp_path / "release_build.json").write_text(json.dumps(build))
    shutil.copyfile(SMOKE / "surface.csv", tmp_path / "surface.csv")
    return tmp_path


# --- adapter -------------------------------------------------------------------------------------

def test_surface_csv_values_match_raw_rows():
    rows = read_surface_csv(SMOKE / "surface.csv")
    with open(SMOKE / "surface.csv", newline="") as f:
        raw = list(csv.DictReader(f))
    assert len(rows) == len(raw) == 4
    for got, src in zip(rows, raw):
        assert set(got) == set(METRIC_FIELDS)
        assert got["errors"] == int(src["errors"]) and got["shots"] == int(src["shots"])
        assert got["ler"] == float(src["ler"]) == got["errors"] / got["shots"]
        assert got["ler_lo"] <= got["ler"] <= got["ler_hi"]
        assert got["throughput_sps"] == float(src["throughput_sps"])
        assert got["lat_p50_us"] == float(src["lat_p50_us"])


@pytest.mark.parametrize("change", ["drop", "rename", "add"])
def test_unexpected_benchmark_columns_are_rejected(tmp_path, change):
    lines = (SMOKE / "surface.csv").read_text().splitlines()
    cols = lines[0].split(",")
    if change == "drop":
        cols.remove("lat_p99_us")
    elif change == "rename":
        cols[cols.index("lat_p50_us")] = "lat_p50_ms"
    else:
        cols.append("new_metric")
    bad = tmp_path / "surface.csv"
    bad.write_text("\n".join([",".join(cols), *lines[1:]]) + "\n")
    with pytest.raises(ReportError, match="unexpected columns"):
        read_surface_csv(bad)


def test_unexpected_benchmark_protocol_is_rejected(tmp_path):
    shutil.copytree(SMOKE, tmp_path / "r")
    meta = json.loads((tmp_path / "r/meta.json").read_text())
    meta["benchmark_protocol"] = "median-paired-v3"
    (tmp_path / "r/meta.json").write_text(json.dumps(meta))
    with pytest.raises(ReportError, match="benchmark_protocol"):
        make_report(results_dir=tmp_path / "r")


def test_junit_counts(tmp_path):
    assert parse_junit(FIX / "junit.xml") == {"passed": 33, "failed": 0, "skipped": 4}
    x = tmp_path / "j.xml"
    x.write_text('<testsuites><testsuite tests="10" failures="2" errors="1" skipped="3"/></testsuites>')
    assert parse_junit(x) == {"passed": 4, "failed": 3, "skipped": 3}


def test_measured_report_requires_harness_commit_match():
    assert make_report(source_kind="measured")["sourceKind"] == "measured"
    with pytest.raises(ReportError, match="benchmark ran at commit"):
        make_report(source_kind="measured", commit_sha=OTHER_SHA)


def test_report_carries_conditions_and_provenance():
    r = make_report(results_label="results/release-smoke")
    c = r["benchmark"]["conditions"]
    assert c["profile"] == "quick" and c["throughputReps"] == 3 and c["surfaceModes"] == ["none"]
    assert c["harnessCommit"] == "e9de2f3"
    assert "results/release-smoke/surface.csv" in r["provenance"]["sourcePaths"]
    assert r["environment"]["device"] == "cpu"


# --- schema --------------------------------------------------------------------------------------

@pytest.mark.parametrize("mutate, msg", [
    (lambda r: r.update(schemaVersion=2), "schemaVersion"),
    (lambda r: r.update(reportId=" "), "reportId"),
    (lambda r: r.update(commitSha=HARNESS_SHA[:7]), "commitSha"),
    (lambda r: r.update(generatedAt="2026-10-21 14:19:57"), "generatedAt"),
    (lambda r: r.update(sourceKind="estimated"), "sourceKind"),
    (lambda r: r["tests"].update(failed=-1), "tests.failed"),
    (lambda r: r["benchmark"]["metrics"][0].pop("ler_hi"), "metrics"),
    (lambda r: r["benchmark"]["metrics"][0].update(errors="23"), "errors"),
    (lambda r: r["benchmark"].update(rawFile="../../etc/passwd"), "rawFile"),
    (lambda r: r.pop("provenance"), "provenance"),
    (lambda r: r.update(speedup=2.0), "unexpected top-level"),
])
def test_invalid_reports_are_rejected(mutate, msg):
    r = make_report()
    mutate(r)
    with pytest.raises(ReportError, match=msg):
        validate_report(r)


def test_bundle_rejects_build_commit_mismatch(tmp_path):
    r = make_report()
    write_bundle(tmp_path, r, {"commitSha": OTHER_SHA, "reportId": r["reportId"]})
    with pytest.raises(ReportError, match="commitSha does not match"):
        load_bundle(tmp_path)


# --- viewer --------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from release_app.app import app

    monkeypatch.setenv("RELEASE_DATA_DIR", str(tmp_path))
    return TestClient(app)


def test_routes_with_valid_bundle(client, tmp_path):
    r = make_report()
    write_bundle(tmp_path, r)
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json() == {"status": "ok", "commitSha": HARNESS_SHA, "reportId": r["reportId"],
                        "reportSchemaVersion": 1}
    assert client.get("/api/reports/latest").json() == r
    raw = client.get("/api/reports/latest/raw")
    assert raw.status_code == 200 and raw.content == (SMOKE / "surface.csv").read_bytes()
    page = client.get("/")
    assert page.status_code == 200
    for text in (HARNESS_SHA, "FIXTURE", "33 passed, 0 failed, 4 skipped", "Measurement conditions",
                 "median-paired-v2", "/api/reports/latest/raw"):
        assert text in page.text


def test_raw_route_takes_no_path_argument(client, tmp_path):
    write_bundle(tmp_path, make_report())
    a = client.get("/api/reports/latest/raw?path=../release_build.json")
    assert a.content == (SMOKE / "surface.csv").read_bytes()
    assert client.get("/api/reports/latest/raw/release_build.json").status_code == 404


def test_historical_label_is_visible(client, tmp_path):
    write_bundle(tmp_path, make_report(source_kind="historical"))
    assert "HISTORICAL" in client.get("/").text


def test_missing_bundle_is_unavailable(client):
    assert client.get("/health").status_code == 503
    assert client.get("/api/reports/latest").status_code == 503
    assert client.get("/api/reports/latest/raw").status_code == 503
    page = client.get("/")
    assert page.status_code == 503 and "Report unavailable" in page.text


def test_invalid_bundle_is_unavailable(client, tmp_path):
    r = make_report()
    r["schemaVersion"] = 2
    write_bundle(tmp_path, r)
    h = client.get("/health")
    assert h.status_code == 503 and h.json()["status"] == "unavailable"
    assert client.get("/").status_code == 503


def test_oversized_raw_file_is_not_served(client, tmp_path):
    write_bundle(tmp_path, make_report())
    (tmp_path / "surface.csv").write_bytes(b"x" * 1_000_001)
    assert client.get("/api/reports/latest/raw").status_code == 503


# --- build script --------------------------------------------------------------------------------

def test_build_script_writes_loadable_bundle(tmp_path):
    out = tmp_path / "data"
    subprocess.run([sys.executable, "scripts/build_release_report.py", "--junit", str(FIX / "junit.xml"),
                    "--results-dir", str(SMOKE), "--command", "fixture", "--source-kind", "fixture",
                    "--commit", HARNESS_SHA, "--out-dir", str(out)], cwd=ROOT, check=True)
    report, build, raw = load_bundle(out)
    assert build["commitSha"] == report["commitSha"] == HARNESS_SHA
    assert report["sourceKind"] == "fixture"
    assert "release_app/tests/fixtures/smoke/surface.csv" in report["provenance"]["sourcePaths"]
