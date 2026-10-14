"""Run the bounded CPU smoke benchmark and bundle a validated release report.

Writes into --out-dir (default release_app/data):
  release_report.json  the report (schema version 1)
  release_build.json   commit / report identity used by /health
  surface.csv          the raw benchmark output the report was built from

  python scripts/build_release_report.py --junit test-results/junit.xml
  python scripts/build_release_report.py --results-dir <dir> --source-kind fixture --junit <xml>
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release_app.bundle import FAMILIES, load_benchmark_bundle, validate_run_id, write_benchmark_bundle  # noqa: E402
from release_app.report import ReportError, build_report, load_bundle, utc_now  # noqa: E402

BASELINE_URL = "https://github.com/dakshverma-dev/ParityBridge"
SMOKE_TIMEOUT_S = 180
DEFAULT_BUNDLE_ROOT = ROOT / "release_app" / "data" / "runs"


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def run_smoke(raw_root: Path, run_id: str, family: str, *, capture_evidence: bool) -> tuple[Path, str]:
    args = ["scripts/run_benchmarks.py", "--profile", "quick", "--device", "cpu", "--tag", run_id,
            "--only", family, "--reps", "3"]
    if family == "surface":
        args += ["--surface-modes", "none"]
    if capture_evidence:
        args += ["--capture-evidence"]
    cmd = ["python", *args, "--out-root", str(raw_root)]
    command = subprocess.list2cmdline(cmd) if os.name == "nt" else shlex.join(cmd)
    print("running:", command, flush=True)
    try:
        subprocess.run([sys.executable, *cmd[1:]], cwd=ROOT, check=True, timeout=SMOKE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        sys.exit(f"smoke benchmark exceeded {SMOKE_TIMEOUT_S} s")
    except subprocess.CalledProcessError as e:
        sys.exit(f"smoke benchmark failed with exit code {e.returncode}")
    return raw_root / run_id, command


def create_smoke(root: Path, run_id: str, family: str) -> Path:
    validate_run_id(run_id)
    with TemporaryDirectory(prefix="paritybridge-") as scratch:
        results, command = run_smoke(Path(scratch), run_id, family, capture_evidence=True)
        return write_benchmark_bundle(root, run_id, results, family=family, source_kind="measured", command=command)


def bundle_main() -> None:
    parser = argparse.ArgumentParser(description="Create or validate a versioned ParityBridge benchmark bundle")
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create", help="run a CPU smoke benchmark or import recorded data")
    create.add_argument("--family", choices=FAMILIES, required=True)
    create.add_argument("--run-id", default=None)
    create.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    create.add_argument("--results-dir", type=Path)
    create.add_argument("--command", help="command that produced the recorded data")
    create.add_argument("--source-kind", choices=("fixture", "historical"), help="required when importing data")
    validate = sub.add_parser("validate", help="validate all metadata, metrics and artifact hashes")
    validate.add_argument("bundle", type=Path)
    demo = sub.add_parser("demo", help="measure two runs per code family and start the local viewer")
    demo.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    demo.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    try:
        if args.action == "demo":
            if not 1 <= args.port <= 65535:
                demo.error("--port must be between 1 and 65535")
            run_demo(args.bundle_root, args.port)
            return
        if args.action == "validate":
            run = load_benchmark_bundle(args.bundle)
            manifest = run["manifest"]
            print(f"valid {manifest['source_kind']} bundle {manifest['run_id']} ({len(run['rows'])} metric rows)")
            return
        run_id = validate_run_id(args.run_id if args.run_id is not None else f"{args.family}-{uuid4().hex[:12]}")
        if args.results_dir is not None:
            if not args.source_kind or not args.command:
                create.error("--results-dir requires --source-kind and --command")
            result = write_benchmark_bundle(args.bundle_root, run_id, args.results_dir, family=args.family,
                                            source_kind=args.source_kind, command=args.command)
        else:
            if args.source_kind or args.command:
                create.error("--source-kind and --command are for recorded imports")
            result = create_smoke(args.bundle_root, run_id, args.family)
    except (OSError, ValueError) as exc:
        sys.exit(f"bundle rejected: {exc}")
    print(f"wrote {result}")


def run_demo(root: Path, port: int) -> None:
    import uvicorn

    suffix = uuid4().hex[:8]
    for family in FAMILIES:
        for side in ("a", "b"):
            print(f"wrote {create_smoke(root, f'{family}-{suffix}-{side}', family)}", flush=True)
    os.environ["PARITYBRIDGE_BUNDLE_ROOT"] = str(root.resolve())
    print(f"Open http://127.0.0.1:{port}/compare", flush=True)
    uvicorn.run("release_app.app:app", host="127.0.0.1", port=port)


def legacy_main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--junit", required=True, help="pytest JUnit XML from the test stage")
    ap.add_argument("--results-dir", help="use an existing benchmark folder instead of running the smoke run")
    ap.add_argument("--command", help="command that produced --results-dir (required with it)")
    ap.add_argument("--source-kind", choices=["measured", "fixture", "historical"], default="measured")
    ap.add_argument("--commit", default=os.environ.get("CI_COMMIT_SHA"))
    ap.add_argument("--pipeline-url", default=os.environ.get("CI_PIPELINE_URL", ""))
    ap.add_argument("--out-dir", default=str(ROOT / "release_app" / "data"))
    a = ap.parse_args()

    if a.results_dir and not a.command:
        ap.error("--command is required with --results-dir")
    if not a.results_dir and a.source_kind != "measured":
        ap.error("a fresh smoke run is always 'measured'; use --results-dir for fixture/historical data")

    commit = a.commit or git_head()
    with TemporaryDirectory(prefix="paritybridge-release-") as scratch:
        if a.results_dir:
            results_dir = (ROOT / a.results_dir).resolve()
            label = results_dir.relative_to(ROOT).as_posix() if results_dir.is_relative_to(ROOT) else results_dir.name
            command = a.command
        else:
            results_dir, command = run_smoke(Path(scratch), "release-smoke", "surface", capture_evidence=False)
            label = "results/release-smoke"
        try:
            report = build_report(results_dir=results_dir, results_label=label, junit=a.junit, commit_sha=commit,
                                  command=command, source_kind=a.source_kind, baseline_url=BASELINE_URL,
                                  pipeline_url=a.pipeline_url)
            publish_legacy(Path(a.out_dir), results_dir, report, a.pipeline_url)
        except ReportError as e:
            sys.exit(f"report rejected: {e}")


def publish_legacy(out: Path, results_dir: Path, report: dict, pipeline_url: str) -> None:
    commit = report["commitSha"]
    image = os.environ.get("CI_REGISTRY_IMAGE")
    build = {
        "commitSha": commit,
        "reportId": report["reportId"],
        "builtAt": utc_now(),
        "image": f"{image}:{commit}" if image else None,
        "pipelineUrl": pipeline_url,
    }

    t = report["tests"]
    if t["failed"]:
        sys.exit("test stage reported failures; release report is not verified")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(results_dir / "surface.csv", out / "surface.csv")
    (out / "release_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "release_build.json").write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
    load_bundle(out)  # the bundle the viewer will serve must load cleanly
    print(f"wrote {out}: report {report['reportId']} ({report['sourceKind']}), commit {commit}, "
          f"tests {t['passed']} passed / {t['failed']} failed / {t['skipped']} skipped, "
          f"{len(report['benchmark']['metrics'])} metric rows")


if __name__ == "__main__":
    if sys.argv[1:2] in (["create"], ["validate"], ["demo"]):
        bundle_main()
    else:
        legacy_main()
