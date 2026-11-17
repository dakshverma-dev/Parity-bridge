"""Experimental FP16 Min-Sum belief propagation kernel."""
import numpy as np

def run_fp16_bp(llr):
    return np.asarray(llr, dtype=np.float16)
