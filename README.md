# qechybrid: GPU-accelerated hybrid quantum error-correction decoding

Quantum error correction needs fast classical decoding. This research repo measures
how much batch throughput a GPU pre-decoder can gain, and what decoding accuracy it costs.

```text
syndrome → parallel pre-decoder → residual syndrome → strong global decoder → prediction
```

## Quick start (local, CPU, virtual environment)

To reproduce the CPU benchmarks, create and activate a Python virtual environment and install PyTorch CPU:

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev]"
python -m pytest -q
```
