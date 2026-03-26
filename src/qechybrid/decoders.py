"""Decoder wrappers: PyMatching, CPU BP+OSD (ldpc), and the hybrid accelerated-BP -> OSD fallback."""
from __future__ import annotations

import numpy as np
import pymatching

class MatchingDecoder:
    def __init__(self, circuit):
        dem = circuit.detector_error_model(decompose_errors=True)
        self.m = pymatching.Matching.from_detector_error_model(dem)
