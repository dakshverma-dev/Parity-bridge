import numpy as np

def percentiles_us(times_s) -> dict[str, float]:
    arr = np.asarray(times_s, dtype=np.float64) * 1e6
    if len(arr) == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }
