# Build log — ParityBridge Release Assistant

## Starting point

- Original repository: https://github.com/dakshverma-dev/ParityBridge
- Imported with full history (51 commits on `main`, plus branches `codex/benchmark-validation` and `pranav/hybrid-validation-polish`).
- Starting commit: `e9de2f3ac645bf9ed0b6a50ad86c2e48ff193bdf` (2026-10-08, "Merge pull request #4 …"), tagged `imported-baseline`.
- Already present before this work: the `qechybrid` package (surface-code and BB qLDPC decoding pipeline), 4 test modules, the benchmark harness `scripts/run_benchmarks.py`, MIT licence with NOTICE and `LICENSES/`, and a GitHub Actions workflow (`.github/workflows/ci.yml`: tests on Python 3.11/3.12, qLDPC smoke benchmark, site build).

## Baseline result (2026-10-21)

Environment: Windows 11 x86-64, CPython 3.13.7, CPU only, installed from `requirements-lock.txt` with `torch==2.14.1+cpu`.

```text
python -m pip install torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
python -m pytest -q
```

Result: **33 passed, 4 skipped** in about 33 s. No setup fixes needed. The skips are 3 CUDA-only tests (no CUDA PyTorch) and 1 test that needs a local clone of NVIDIA/Ising-Decoding.

## Findings that change the pack's plan

- `run_benchmarks.py` rejects `--reps` below 3, so the smoke run uses `--reps 3`, not one repetition.
- Smoke command: `python scripts/run_benchmarks.py --profile quick --device cpu --tag release-smoke --only surface --surface-modes none --reps 3`. It took about 4 s locally, well inside the three-minute limit.
- Its `surface.csv` has 33 columns under `benchmark_protocol = "median-paired-v2"`. The report adapter pins that exact header and protocol.

## New work

| Date | Change |
|---|---|
| 2026-10-21 | `release_app/report.py`: schema v1 validation, `surface.csv` adapter with a pinned header, JUnit test counts, bundle loader. Standard library only. |
| 2026-10-21 | `release_app/app.py`: FastAPI viewer with `/`, `/health`, `/api/reports/latest` and `/api/reports/latest/raw`. |
| 2026-10-21 | `scripts/build_release_report.py`: runs the bounded smoke benchmark (180 s timeout) and writes `release_report.json`, `release_build.json` and `surface.csv`. |
| 2026-10-21 | `release_app/tests/test_report.py`: 27 tests. `pyproject.toml` testpaths now include `release_app/tests`. Full suite: 60 passed, 4 skipped. |
