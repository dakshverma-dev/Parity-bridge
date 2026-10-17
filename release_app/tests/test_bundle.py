import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from release_app.bundle import _attach_shots, load_benchmark_bundle, load_saved_run, point, write_benchmark_bundle
from release_app.report import ReportError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "smoke"
BUILDER = ROOT / "scripts" / "build_release_report.py"


@pytest.fixture
def recorded(tmp_path):
    return write_benchmark_bundle(tmp_path, "sample", FIXTURE, family="surface", source_kind="fixture",
                                  command="fixture generated with the quick profile")


def _change_json(path, modify):
    value = json.loads(path.read_text(encoding="utf-8"))
    modify(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def _reseal(directory, name):
    digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    _change_json(directory / "manifest.json", lambda m: m["artifacts"].update({name: digest}))


def test_fixture_and_cli_validation(recorded):
    result = subprocess.run([sys.executable, str(BUILDER), "validate", str(recorded)], check=True,
                            capture_output=True, text=True)
    assert "valid fixture bundle sample (4 metric rows)" in result.stdout
    run = load_saved_run(recorded.parent, "sample")
    assert run["manifest"]["harness_sha"] == "e9de2f3"
    assert run["rows"][0]["errors"] == 23
    assert (recorded / "surface.csv").read_bytes() == (FIXTURE / "surface.csv").read_bytes()
    assert "shot_sha256" not in run["rows"][0]


def test_fixture_cannot_be_promoted_to_measured_by_import(tmp_path):
    result = subprocess.run([sys.executable, str(BUILDER), "create", "--family", "surface",
                             "--bundle-root", str(tmp_path), "--results-dir", str(FIXTURE),
                             "--source-kind", "measured", "--command", "fixture"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_corrupt_artifact_rejected(recorded):
    with (recorded / "surface.csv").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ReportError, match="hash mismatch for surface.csv"):
        load_benchmark_bundle(recorded)


def test_nonfinite_csv_rejected_even_with_correct_hash(recorded):
    path = recorded / "surface.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["lat_p50_us"] = "NaN"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    _reseal(recorded, path.name)
    with pytest.raises(ReportError, match="finite"):
        load_benchmark_bundle(recorded)


def test_rejects_malformed_metadata_even_with_correct_hash(recorded):
    path = recorded / "meta.json"
    _change_json(path, lambda m: m["config"]["surface"].update(shots=True))
    _reseal(recorded, path.name)
    with pytest.raises(ReportError, match="shots"):
        load_benchmark_bundle(recorded)


@pytest.mark.parametrize("run_id", ["../sample", "sub/sample", r"..\sample", "con", "sample:stream", ".staging-hidden"])
def test_unsafe_run_names_are_rejected(recorded, run_id):
    with pytest.raises(ReportError, match="safe name"):
        load_saved_run(recorded.parent, run_id)


def test_manifest_cannot_point_outside_bundle(recorded):
    _change_json(recorded / "manifest.json", lambda m: m["artifacts"].update({"../meta.json": "0" * 64}))
    with pytest.raises(ReportError, match="unsafe artifact"):
        load_benchmark_bundle(recorded)


def test_cancelled_publish_and_parse_error_leave_no_new_run(tmp_path, monkeypatch):
    def cancel(*_):
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", cancel)
        with pytest.raises(KeyboardInterrupt):
            write_benchmark_bundle(tmp_path, "cancelled", FIXTURE, family="surface", source_kind="fixture",
                                   command="fixture")
    assert list(tmp_path.iterdir()) == []
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE, broken)
    (broken / "surface.csv").write_text("invalid\n", encoding="utf-8")
    with pytest.raises(ReportError, match="unexpected columns"):
        write_benchmark_bundle(tmp_path, "rejected", broken, family="surface", source_kind="fixture",
                               command="fixture")
    assert list(tmp_path.iterdir()) == [broken]


def test_published_run_cannot_be_replaced(recorded):
    with pytest.raises(ReportError, match="already exists"):
        write_benchmark_bundle(recorded.parent, "sample", FIXTURE, family="surface", source_kind="historical",
                               command="archived command")
    assert load_benchmark_bundle(recorded)["manifest"]["source_kind"] == "fixture"


def test_shot_evidence_must_reproduce_aggregate_counts(recorded):
    row = load_benchmark_bundle(recorded)["rows"][0]
    entry = {key: row[key] for key in ("code", "d", "rounds", "p", "decoder")}
    entry.update(shot_sha256="0" * 64, logical_failures="0" * row["shots"], diagnostic_cpu_fallback_s=None)
    with pytest.raises(ReportError, match="logical error and shot counts"):
        _attach_shots(json.dumps([entry]).encode(), {(*point(row), row["decoder"]): row})


def test_unpublished_directories_cannot_be_opened_in_viewer(recorded):
    hidden = recorded.parent / ".staging-run"
    recorded.rename(hidden)
    with pytest.raises(ReportError, match="safe name"):
        load_saved_run(hidden.parent, hidden.name)
