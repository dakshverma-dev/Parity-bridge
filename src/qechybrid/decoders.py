"""Decoder wrappers: PyMatching, CPU BP+OSD (ldpc), and the hybrid accelerated-BP -> OSD fallback."""
from __future__ import annotations

import numpy as np
import pymatching

class MatchingDecoder:
    def __init__(self, circuit):
        dem = circuit.detector_error_model(decompose_errors=True)
        self.m = pymatching.Matching.from_detector_error_model(dem)

    def decode_batch(self, dets: np.ndarray) -> np.ndarray:
        if len(dets) == 0:
            return np.zeros((0, 1), np.uint8)
        return np.asarray(self.m.decode_batch(dets.astype(np.uint8)), dtype=np.uint8)

    def decode_one(self, det: np.ndarray) -> np.ndarray:
        return np.asarray(self.m.decode(det.astype(np.uint8)), dtype=np.uint8)
