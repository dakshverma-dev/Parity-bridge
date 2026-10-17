from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from release_app.app import app
from release_app.bundle import load_benchmark_bundle, write_benchmark_bundle
from release_app.comparison import compare_runs
from release_app.report import ReportError

from .test_bundle import FIXTURE


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv("PARITYBRIDGE_BUNDLE_ROOT", str(tmp_path))
    return tuple(write_benchmark_bundle(tmp_path, name, FIXTURE, family="surface", source_kind=kind,
                                        command="quick CPU surface")
                 for name, kind in (("example", "fixture"), ("archive", "historical")))


def test_comparison_views_preserve_metrics_and_labels(saved):
    client = TestClient(app)
    query = {"left": "example", "right": "archive"}
    response = client.get("/api/compare", params=query)
    assert response.status_code == 200
    result = response.json()
    assert result["left"]["source_kind"] == "fixture"
    assert result["right"]["source_kind"] == "historical"
    row = result["rows"][0]
    assert row["left"]["logical_errors"] == 23
    assert row["left"]["shot_count"] == 20000
    assert row["left"]["batch_throughput_shots_per_s"] == 1071145.4828324865
    assert row["left"]["wilson_95"][0] < 23 / 20000 < row["left"]["wilson_95"][1]
    assert row["paired_disagreements"] is None
    assert row["speed_ratios"] is None
    assert "measured runs" in row["speed_ratio_reason"]
    page = client.get("/compare", params=query)
    assert page.status_code == 200
    assert "example (fixture)" in page.text
    assert "Batch shots/s" in page.text and "Single-shot" in page.text
    markdown = client.get("/api/compare.md", params=query)
    assert markdown.status_code == 200 and markdown.headers["content-type"].startswith("text/markdown")
    assert "23/20000" in markdown.text
    assert client.post("/api/compare", params=query).status_code == 405


def test_unavailable_explanation_and_traversal(saved):
    client = TestClient(app)
    query = {"left": "../example", "right": "archive"}
    for endpoint in ("/compare", "/api/compare", "/api/compare.md"):
        result = client.get(endpoint, params=query)
        assert result.status_code == 422 and "safe name" in result.text
    (saved[0] / "surface.csv").write_bytes(b"invalid")
    assert "hash mismatch" in client.get("/compare", params={"left": "example", "right": "archive"}).text


@pytest.mark.parametrize("key, value, message", [
    ("code_family", "qldpc", "code family"),
    ("noise_model", "other", "noise model"),
    ("benchmark_protocol", "other", "benchmark protocol"),
])
def test_incompatible_workload(saved, key, value, message):
    left, right = map(load_benchmark_bundle, saved)
    right["manifest"][key] = value
    with pytest.raises(ReportError, match=message):
        compare_runs(left, right)


def test_incompatible_parameter_grid(saved):
    left, right = map(load_benchmark_bundle, saved)
    right["rows"].pop()
    with pytest.raises(ReportError, match="different parameter points"):
        compare_runs(left, right)


def test_measured_slowdown_and_real_paired_disagreements(saved):
    # Small synthetic failure lists exercise the comparator without timing assertions.
    left = load_benchmark_bundle(saved[0])
    left["manifest"]["source_kind"] = "measured"
    left["metadata"]["cpu_model"] = "Host CPU"
    left["rows"] = [left["rows"][0]]
    left["rows"][0].update(shot_sha256="a" * 64, logical_failures="010", errors=1, shots=3,
                           throughput_sps=100.0, lat_p50_us=5.0)
    right = deepcopy(left)
    right["rows"][0].update(logical_failures="100", throughput_sps=75.0, lat_p50_us=10.0)
    point = compare_runs(left, right)["rows"][0]
    assert point["paired_disagreements"] == {"left_only": 1, "right_only": 1, "total": 2}
    assert point["speed_ratios"] == {"batch_throughput_right_over_left": 0.75, "single_shot_p50_left_over_right": 0.5}

    right["metadata"]["cpu_model"] = "Different CPU"
    point = compare_runs(left, right)["rows"][0]
    assert point["speed_ratios"] is None and "Hardware" in point["speed_ratio_reason"]
    assert point["paired_disagreements"]["total"] == 2

    right["metadata"]["cpu_model"] = "Host CPU"
    right["metadata"]["torch_num_threads"] += 1
    point = compare_runs(left, right)["rows"][0]
    assert point["speed_ratios"] is None and "Timing settings" in point["speed_ratio_reason"]

    right["metadata"]["torch_num_threads"] -= 1
    right["rows"][0]["shot_sha256"] = "b" * 64
    point = compare_runs(left, right)["rows"][0]
    assert point["paired_disagreements"] is None and point["speed_ratios"] is None
    assert "Ordered shot identity" in point["speed_ratio_reason"]


def test_selected_decoders_must_cover_both_runs(saved):
    left, right = map(load_benchmark_bundle, saved)
    for row in right["rows"]:
        row["decoder"] = "alternative"
    with pytest.raises(ReportError, match="No matching decoder rows"):
        compare_runs(left, right)
    with pytest.raises(ReportError, match="Select a decoder for each run"):
        compare_runs(left, right, "pymatching (CPU)")
    rows = compare_runs(left, right, "pymatching (CPU)", "alternative")["rows"]
    assert len(rows) == 4
    assert all(row["right_decoder"] == "alternative" for row in rows)
