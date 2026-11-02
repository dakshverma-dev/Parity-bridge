# qechybrid: GPU-accelerated hybrid quantum error-correction decoding

Quantum error correction needs fast classical decoding. This research repo measures
how much batch throughput a GPU pre-decoder can gain, and what decoding accuracy it costs.

```text
syndrome → parallel pre-decoder → residual syndrome → strong global decoder → prediction
```

## Local benchmark workbench

The private workbench extends the existing release builder and FastAPI viewer.
It saves evidence from surface-code and bivariate-bicycle qLDPC CPU smoke runs
and compares compatible runs with JSON and Markdown exports.

From the repository root, create and activate a Python virtual environment.
The clean verification used CPython 3.13.7 on Windows x86-64.

```bash
python -m venv .venv
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev]" -r release_app/requirements.txt httpx
python -m pytest -q -rs
python scripts/build_release_report.py demo
```

Open the loopback viewer at http://127.0.0.1:8000/compare.
