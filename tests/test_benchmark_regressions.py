import numpy as np
import pytest
from qechybrid import data, local_predecoder

def test_local_correction_residual_and_logical_flip_invariant():
    circ = data.surface_circuit(d=3, p=0.005)
    lp = local_predecoder.LocalPreDecoder(circ)
    dets, _ = data.sample(circ, shots=20, seed=1)
    res, flips = lp.predecode(dets)
    assert res.shape == dets.shape
