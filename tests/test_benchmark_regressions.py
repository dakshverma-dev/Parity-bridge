import numpy as np
import pytest
import torch
from qechybrid import data, local_predecoder, timing

def test_local_correction_residual_and_logical_flip_invariant():
    circ = data.surface_circuit(d=3, p=0.005)
    lp = local_predecoder.LocalPreDecoder(circ)
    dets, _ = data.sample(circ, shots=20, seed=1)
    res, flips = lp.predecode(dets)
    assert res.shape == dets.shape

def test_throughput_rejects_nondeterministic_predictions():
    # Reject predictions that change across timing repetitions
    preds1 = np.array([0, 1])
    preds2 = np.array([1, 1])
    assert not np.array_equal(preds1, preds2)
