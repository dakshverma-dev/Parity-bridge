"""qLDPC code construction + code-capacity noise (bivariate bicycle codes)."""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

def _shift(n: int, k: int) -> np.ndarray:
    return np.roll(np.eye(n, dtype=np.int64), k, axis=1)

def _poly(terms, x, y) -> np.ndarray:
    n = x.shape[0]
    out = np.zeros((n, n), dtype=np.int64)
    for var, power in terms:
        base = x if var == "x" else y
        out += np.linalg.matrix_power(base, power)
    return (out % 2).astype(np.uint8)

@dataclass
class BBCode:
    name: str
    hx: np.ndarray
    hz: np.ndarray
    n: int
    k: int

def bb_72_12_6() -> BBCode:
    x = np.kron(_shift(6, 1), np.eye(6, dtype=np.int64))
    y = np.kron(np.eye(6, dtype=np.int64), _shift(6, 1))
    a_terms = [("x", 3), ("y", 1), ("y", 2)]
    b_terms = [("y", 3), ("x", 1), ("x", 2)]
    A, B = _poly(a_terms, x, y), _poly(b_terms, x, y)
    hx = np.hstack([A, B]).astype(np.uint8)
    hz = np.hstack([B.T, A.T]).astype(np.uint8)
    return BBCode("bb72", hx, hz, 72, 12)
