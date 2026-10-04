"""Compare saved benchmark evidence without changing the reported measurements."""
from __future__ import annotations

from math import isfinite

from .bundle import HARDWARE, TIMING_ENV, point
from .report import ReportError

METRICS = {
    "logical_errors": "errors", "shot_count": "shots", "logical_error_rate": "ler",
    "batch_throughput_shots_per_s": "throughput_sps", "batch_repetitions": "throughput_reps",
    "batch_times_s": "throughput_times_s",
    "single_shot_p50_us": "lat_p50_us", "single_shot_p95_us": "lat_p95_us", "single_shot_p99_us": "lat_p99_us",
    "batch_256_latency_ms": "lat_b256_ms", "accept_rate": "accept_rate",
    "stage1_s": "t_stage1_s", "global_decode_s": "t_global_s",
    "diagnostic_cpu_fallback_s": "diagnostic_cpu_fallback_s",
}


def _metrics(row):
    return {**{key: row.get(field) for key, field in METRICS.items()},
            "wilson_95": [row["ler_lo"], row["ler_hi"]], "timing_device": row["device"],
            "transfer_cost": ("no device transfers in CPU run" if row["device"] == "cpu"
                              else "included in end-to-end timings, no standalone transfer measurement")}


def _performance_reason(left, right):
    if any(run["manifest"]["source_kind"] != "measured" for run in (left, right)):
        return "Speed ratios require measured runs with recorded hardware and timing settings."
    lm, rm = left["metadata"], right["metadata"]
    if any(lm.get(key) != rm.get(key) for key in HARDWARE):
        return "Hardware or the execution environment differs."
    family = left["manifest"]["code_family"]
    if (any(lm.get(key) != rm.get(key) for key in (*TIMING_ENV, "decoder_order", "python", "dependencies"))
            or lm["config"][family] != rm["config"][family]):
        return "Timing settings, benchmark configuration, or dependency versions differ."
    return None


def _compare_rows(left, right, performance_reason):
    paired = (left.get("shot_sha256") is not None and left["shot_sha256"] == right.get("shot_sha256")
              and left["shots"] == right["shots"])
    disagreements = None
    if paired:
        total = sum(a != b for a, b in zip(left["logical_failures"], right["logical_failures"], strict=True))
        left_only = (total + left["errors"] - right["errors"]) // 2
        disagreements = {"left_only": left_only, "right_only": total - left_only, "total": total}

    if performance_reason is None and not paired:
        # Different noise draws can change decoder work, particularly the cost of fallback.
        performance_reason = "Ordered shot identity could not be verified."
    if performance_reason is None and left["device"] != right["device"]:
        performance_reason = "Decoder timing devices differ."
    ratios = None
    if performance_reason is None:
        batch = right["throughput_sps"] / left["throughput_sps"]
        latency = left["lat_p50_us"] / right["lat_p50_us"]
        if all(isfinite(value) and value > 0 for value in (batch, latency)):
            ratios = {"batch_throughput_right_over_left": batch, "single_shot_p50_left_over_right": latency}
        else:
            performance_reason = "Speed ratios are outside the representable range."
    return {
        "point": dict(zip(("code", "d", "rounds", "p"), point(left))),
        "left_decoder": left["decoder"], "right_decoder": right["decoder"],
        "left": _metrics(left), "right": _metrics(right),
        "paired_disagreements": disagreements,
        "pairing_reason": None if paired else "Ordered shot fingerprints or shot counts could not be matched.",
        "speed_ratios": ratios, "speed_ratio_reason": performance_reason,
    }


def compare_runs(left: dict, right: dict, left_decoder: str | None = None, right_decoder: str | None = None) -> dict:
    """Compare common decoder rows or a researcher-selected decoder on each side."""
    lm, rm = (run["manifest"] for run in (left, right))
    for key in ("code_family", "noise_model", "benchmark_protocol"):
        if lm[key] != rm[key]:
            raise ReportError(f"Runs use different {key.replace('_', ' ')} values.")
    left_rows = left["rows"]
    right_rows = right["rows"]
    points = {point(row) for row in left_rows}
    if points != {point(row) for row in right_rows}:
        raise ReportError("Runs cover different parameter points.")
    if (left_decoder is None) != (right_decoder is None):
        raise ReportError("Select a decoder for each run.")

    reason = _performance_reason(left, right)
    right_by_point = {(*point(row), row["decoder"]): row for row in right_rows}
    compared = []
    for row in left_rows:
        if left_decoder is not None and row["decoder"] != left_decoder:
            continue
        other = right_by_point.get((*point(row), right_decoder if right_decoder is not None else row["decoder"]))
        if other is not None:
            compared.append(_compare_rows(row, other, reason))
    if {tuple(row["point"].values()) for row in compared} != points:
        raise ReportError("No matching decoder rows at one or more parameter points. Select a decoder from each run.")
    return {
        "left": {"run_id": lm["run_id"], "source_kind": lm["source_kind"], "harness_sha": lm["harness_sha"]},
        "right": {"run_id": rm["run_id"], "source_kind": rm["source_kind"], "harness_sha": rm["harness_sha"]},
        "code_family": lm["code_family"], "noise_model": lm["noise_model"], "benchmark_protocol": lm["benchmark_protocol"],
        "rows": compared,
    }


def comparison_markdown(result):
    def cell(value):
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.5g}"
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")

    left, right = result["left"], result["right"]
    lines = [
        "# ParityBridge comparison", "",
        f"- Left — {left['run_id']} ({left['source_kind']})",
        f"- Right — {right['run_id']} ({right['source_kind']})",
        f"- Workload — {result['code_family']}, {result['noise_model']}, {result['benchmark_protocol']}", "",
        "| Parameter point | Decoder | Logical errors / shots (Wilson 95%) | Batch shots/s | Single-shot p50 / p95 / p99 (µs) | CPU fallback (s, diagnostic) |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in result["rows"]:
        p = row["point"]
        label = f"{p['code']}, d={p['d']}, rounds={p['rounds']}, p={p['p']}" if p["d"] else f"{p['code']}, p={p['p']}"
        for side in ("left", "right"):
            data = row[side]
            error = f"{data['logical_errors']}/{data['shot_count']} ({cell(data['wilson_95'][0])}–{cell(data['wilson_95'][1])})"
            latency = " / ".join(cell(data[f"single_shot_p{k}_us"]) for k in (50, 95, 99))
            values = (label, f"{side} — {row[f'{side}_decoder']}", error, data["batch_throughput_shots_per_s"],
                      latency, data["diagnostic_cpu_fallback_s"])
            lines.append("| " + " | ".join(map(cell, values)) + " |")
    lines.extend(["", "Speed factors above 1 favor the right-hand run. Wilson intervals are per decoder and point.", ""])
    for row in result["rows"]:
        p = row["point"]
        label = f"{p['code']} d={p['d']} p={p['p']} ({row['left_decoder']} → {row['right_decoder']})"
        ratios = row["speed_ratios"]
        speed = (f"Batch {cell(ratios['batch_throughput_right_over_left'])}×, "
                 f"p50 {cell(ratios['single_shot_p50_left_over_right'])}×."
                 if ratios else row["speed_ratio_reason"])
        counts = row["paired_disagreements"]
        pairs = (f"Paired logical failures differ on {counts['total']} shots "
                 f"({counts['left_only']} left only, {counts['right_only']} right only)."
                 if counts is not None else row["pairing_reason"])
        lines.append(f"- {cell(label)}. {speed} {pairs}")
    transfer_notes = {row[side]["transfer_cost"] for row in result["rows"] for side in ("left", "right")}
    lines.extend(["", "Transfer costs — " + ". ".join(sorted(transfer_notes)) + "."])
    return "\n".join(lines) + "\n"
