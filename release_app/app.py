"""Read-only viewer for saved benchmarks and the legacy latest release report.

The bundle lives in RELEASE_DATA_DIR (default: release_app/data) and holds
release_report.json, release_build.json and the raw CSV the report names.
It is re-read on every request, so a missing or invalid bundle is never served
from a stale in-memory copy.
"""
from __future__ import annotations

import os
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

if not __package__:  # preserve the release image's top-level import
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_app.bundle import load_saved_run, validate_run_id
from release_app.comparison import compare_runs, comparison_markdown
from release_app.report import METRIC_FIELDS, ReportError, load_bundle

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

app = FastAPI(title="ParityBridge Release Report", docs_url=None, redoc_url=None, openapi_url=None)


def data_dir() -> Path:
    return Path(os.environ.get("RELEASE_DATA_DIR") or DEFAULT_DATA_DIR)


def bundle_root() -> Path:
    return Path(os.environ.get("PARITYBRIDGE_BUNDLE_ROOT") or data_dir() / "runs")


def _unavailable(reason: str) -> JSONResponse:
    return JSONResponse({"status": "unavailable", "error": reason}, status_code=503)


@app.get("/health")
def health():
    try:
        report, build, _ = load_bundle(data_dir())
    except ReportError as e:
        return _unavailable(str(e))
    return {"status": "ok", "commitSha": build["commitSha"], "reportId": report["reportId"],
            "reportSchemaVersion": report["schemaVersion"]}


@app.get("/api/reports/latest")
def latest():
    try:
        report, _, _ = load_bundle(data_dir())
    except ReportError as e:
        return _unavailable(str(e))
    return report


@app.get("/api/reports/latest/raw")
def latest_raw():
    try:
        _, _, raw = load_bundle(data_dir())
    except ReportError as e:
        return _unavailable(str(e))
    return FileResponse(raw, media_type="text/csv", filename=raw.name)


_STYLE = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5f5e5a;--line:#dedcd4;--ok:#1f6f43;--bad:#a1271c;--warn:#8a5a00;--warnbg:#fff3d6}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a5a39b;--line:#3a3934;--ok:#6fcf97;--bad:#ff8a7a;--warn:#f2c46b;--warnbg:#3a2f12}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:24px 16px}
h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.05rem;margin:28px 0 8px}
code{font:13px ui-monospace,monospace;overflow-wrap:anywhere}.muted{color:var(--muted)}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.label{display:inline-block;padding:2px 10px;border-radius:4px;font-weight:700;letter-spacing:.04em}
.label.measured{border:1px solid var(--ok);color:var(--ok)}
.label.fixture,.label.historical{background:var(--warnbg);color:var(--warn);border:1px solid var(--warn)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:0}dt{color:var(--muted)}dd{margin:0}
.grid{display:grid;grid-template-columns:2fr 1fr;gap:24px}@media (max-width:800px){.grid{grid-template-columns:1fr}}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:13px;white-space:nowrap}
th,td{border-bottom:1px solid var(--line);padding:4px 8px;text-align:right}th{vertical-align:bottom}
td:nth-child(-n+6),th:nth-child(-n+6){text-align:left}th small{display:block;font-weight:400;color:var(--muted)}
form{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin:16px 0}label{display:grid;gap:4px}
select,button{font:inherit;padding:5px;max-width:100%}a{color:inherit}p{max-width:80ch}
"""


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.3g}" if abs(v) < 1e-2 and v != 0 else f"{v:,.4g}" if abs(v) < 1e4 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _page(body: str, status: int = 200) -> HTMLResponse:
    html = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>ParityBridge Workbench</title><style>{_STYLE}</style></head><body>"
            f"<nav><a href='/compare'>Compare saved runs</a> · <a href='/'>Latest release report</a></nav>"
            f"{body}</body></html>")
    return HTMLResponse(html, status_code=status)


def _comparison(left, right, left_decoder, right_decoder):
    root = bundle_root()
    return compare_runs(load_saved_run(root, left), load_saved_run(root, right), left_decoder, right_decoder)


@app.get("/api/compare")
def comparison_json(left: str, right: str, left_decoder: str | None = None, right_decoder: str | None = None):
    try:
        return _comparison(left, right, left_decoder, right_decoder)
    except ReportError as exc:
        return JSONResponse({"status": "unavailable", "error": str(exc)}, status_code=422)


@app.get("/api/compare.md", response_class=PlainTextResponse)
def comparison_md(left: str, right: str, left_decoder: str | None = None, right_decoder: str | None = None):
    try:
        return PlainTextResponse(comparison_markdown(_comparison(left, right, left_decoder, right_decoder)),
                                 media_type="text/markdown")
    except ReportError as exc:
        return PlainTextResponse(f"Comparison unavailable. {exc}\n", status_code=422)


def _choose(name, label, entries, selected=None, prompt=None):
    options = [f'<option value="">{escape(prompt)}</option>'] if prompt else []
    for value, title in entries:
        mark = " selected" if value == selected else ""
        options.append(f'<option value="{escape(value)}"{mark}>{escape(title)}</option>')
    return f"<label>{label}<select name='{name}' required>{''.join(options)}</select></label>"


def _saved_runs(root):
    entries = []
    if root.is_dir():
        for item in sorted(root.iterdir()):
            try:
                validate_run_id(item.name)
                if not item.is_dir():
                    continue
                meta = load_saved_run(root, item.name)["manifest"]
                label = f"{item.name} ({meta['code_family']}, {meta['source_kind']})"
            except ReportError:
                continue
            entries.append((item.name, label))
    return entries


def _comparison_table(result):
    table = ["<div class=scroll><table><thead><tr><th>Parameter point</th><th>Run and decoder</th>"
             "<th>Logical errors / shots</th><th>Wilson 95%</th><th>Batch shots/s</th>"
             "<th>Single-shot p50 / p95 / p99 (µs)</th><th>CPU fallback (s, diagnostic)</th>"
             "</tr></thead><tbody>"]
    for row in result["rows"]:
        p = row["point"]
        name = f"{p['code']}, d={p['d']}, rounds={p['rounds']}, p={p['p']}" if p["d"] else f"{p['code']}, p={p['p']}"
        for side in ("left", "right"):
            data = row[side]
            latency = " / ".join(_fmt(data[f"single_shot_p{k}_us"]) for k in (50, 95, 99))
            interval = "–".join(f"{bound:.4g}" for bound in data["wilson_95"])
            cells = (
                name, f"{side} · {row[f'{side}_decoder']} ({data['timing_device']})",
                f"{data['logical_errors']:,} / {data['shot_count']:,}", interval,
                _fmt(data["batch_throughput_shots_per_s"]), latency,
                _fmt(data["diagnostic_cpu_fallback_s"]) if data["diagnostic_cpu_fallback_s"] is not None else "—",
            )
            table.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>")
        counts, ratios = row["paired_disagreements"], row["speed_ratios"]
        pairs = (f"{counts['total']} paired disagreements ({counts['left_only']} left only, {counts['right_only']} right only)."
                 if counts is not None else row["pairing_reason"])
        speed = (f"Batch ×{ratios['batch_throughput_right_over_left']:.3g}. "
                 f"Single-shot p50 ×{ratios['single_shot_p50_left_over_right']:.3g}."
                 if ratios else row["speed_ratio_reason"])
        table.append(f"<tr><td colspan='7' class='muted'>{escape(pairs)} {escape(speed)}</td></tr>")
    table.append("</tbody></table></div>")
    notes = {row[side]["transfer_cost"] for row in result["rows"] for side in ("left", "right")}
    table.append(f"<p class=muted>{escape('. '.join(sorted(notes)))}.</p>")
    return "".join(table)


@app.get("/compare", response_class=HTMLResponse)
def comparison_page(left: str | None = None, right: str | None = None,
                    left_decoder: str | None = None, right_decoder: str | None = None):
    root = bundle_root()
    entries = _saved_runs(root)
    body = "<h1>Compare saved runs</h1>"
    if entries:
        body += ("<form method='get' action='/compare'>"
                 + _choose("left", "Left run", entries, left, "Choose a run")
                 + _choose("right", "Right run", entries, right, "Choose a run")
                 + "<button>Load runs</button></form>")
    else:
        body += "<p>No validated runs are available. Create a CPU bundle with the benchmark CLI.</p>"
    if left is None and right is None:
        return _page(body)
    try:
        lr = load_saved_run(root, left)
        rr = load_saved_run(root, right)
    except ReportError as exc:
        return _page(body + f"<h2>Comparison unavailable</h2><p>{escape(str(exc))}</p>", status=422)

    def decoders(run):
        return [(name, name) for name in sorted({row["decoder"] for row in run["rows"]})]

    query = {"left": left, "right": right}
    body += (f"<form method='get' action='/compare'><input type='hidden' name='left' value='{escape(left)}'>"
             f"<input type='hidden' name='right' value='{escape(right)}'>"
             + _choose("left_decoder", "Left decoder", decoders(lr), left_decoder)
             + _choose("right_decoder", "Right decoder", decoders(rr), right_decoder)
             + "<button>Compare decoders</button></form>")
    try:
        result = compare_runs(lr, rr, left_decoder, right_decoder)
    except ReportError as exc:
        return _page(body + f"<h2>Comparison unavailable</h2><p>{escape(str(exc))}</p>", status=422)
    if left_decoder is not None:
        query.update(left_decoder=left_decoder, right_decoder=right_decoder)
    args = escape(urlencode(query))
    body += (f"<h2>{escape(left)} ({result['left']['source_kind']}) vs {escape(right)} ({result['right']['source_kind']})</h2>"
             f"<p>{result['noise_model']} · {result['benchmark_protocol']}</p>"
             "<p>Speed factors above 1 favor the right-hand run. Wilson intervals are per decoder and point.</p>"
             f"<p><a href='/api/compare?{args}'>JSON</a> · <a href='/api/compare.md?{args}'>Markdown</a></p>")
    return _page(body + _comparison_table(result))


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        report, build, raw = load_bundle(data_dir())
    except ReportError as e:
        return _page("<h1>Report unavailable</h1><p class=bad>The bundled release report failed validation.</p>"
                     f"<p><code>{escape(str(e))}</code></p>", status=503)

    kind = report["sourceKind"]
    tests = report["tests"]
    bench = report["benchmark"]
    verified = tests["failed"] == 0 and bench["status"] == "passed"
    kind_note = {
        "measured": "Measured in the pipeline run that built this release.",
        "fixture": "FIXTURE: sample data for testing the viewer. Not a measurement.",
        "historical": "HISTORICAL: an earlier recorded run, not measured for this commit.",
    }[kind]

    head = "".join(f"<th>{escape(k)}<small>{escape(u)}</small></th>" for k, (u, _) in METRIC_FIELDS.items())
    rows = "".join("<tr>" + "".join(f"<td>{escape(_fmt(m[k]))}</td>" for k in METRIC_FIELDS) + "</tr>"
                   for m in bench["metrics"])
    legend = "".join(f"<dt><code>{escape(k)}</code></dt><dd>{escape(d)}</dd>" for k, (_, d) in METRIC_FIELDS.items())
    cond = "".join(f"<dt>{escape(k)}</dt><dd><code>{escape(str(v))}</code></dd>" for k, v in bench["conditions"].items())
    env = report["environment"]
    prov = report["provenance"]
    pipeline = (f"<a href='{escape(prov['pipelineUrl'])}'>{escape(prov['pipelineUrl'])}</a>"
                if prov["pipelineUrl"].startswith("https://") else "<span class=muted>not recorded</span>")

    body = f"""
<h1>ParityBridge release report</h1>
<p><span class="label {kind}">{kind.upper()}</span> <span class=muted>{escape(kind_note)}</span></p>
<dl>
<dt>Commit</dt><dd><code>{escape(build['commitSha'])}</code></dd>
<dt>Verification</dt><dd class="{'ok' if verified else 'bad'}">{'tests and smoke benchmark passed' if verified else 'NOT VERIFIED'}</dd>
<dt>Tests</dt><dd>{tests['passed']} passed, {tests['failed']} failed, {tests['skipped']} skipped</dd>
<dt>Generated</dt><dd>{escape(report['generatedAt'])}</dd>
<dt>Report ID</dt><dd><code>{escape(report['reportId'])}</code></dd>
<dt>Command</dt><dd><code>{escape(report['command'])}</code></dd>
<dt>Environment</dt><dd>Python {escape(env['python'])}, device {escape(env['device'])}, {escape(env['platform'])}</dd>
<dt>Pipeline</dt><dd>{pipeline}</dd>
<dt>Baseline</dt><dd><a href='{escape(prov['baselineUrl'])}'>{escape(prov['baselineUrl'])}</a></dd>
</dl>
<div class=grid>
<section><h2>Benchmark metrics ({escape(bench['status'])})</h2>
<div class=scroll><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>
<p class=muted>Equal error counts between decoders do not show statistical equivalence.</p>
<h2>Column definitions</h2><dl>{legend}</dl></section>
<section><h2>Measurement conditions</h2><dl>{cond}</dl></section>
</div>
<h2>Raw artifacts</h2>
<ul><li><a href="/api/reports/latest/raw">{escape(raw.name)}</a> (raw benchmark output)</li>
<li><a href="/api/reports/latest">release_report.json</a></li><li><a href="/health">/health</a></li></ul>
"""
    return _page(body)
