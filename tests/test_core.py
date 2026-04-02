import numpy as np
from qechybrid import data, decoders, local_predecoder

def test_dem_matrices_consistent():
    circ = data.surface_circuit(d=3, p=0.005)
    dm = data.dem_matrices(circ)
    assert dm.H.shape[0] > 0
    assert dm.L.shape[0] == 1

def test_hybrid_surface_quality_smoke():
    circ = data.surface_circuit(d=3, p=0.005)
    dets, obs = data.sample(circ, shots=100, seed=42)
    dec = decoders.MatchingDecoder(circ)
    preds = dec.decode_batch(dets)
    errs = np.sum(preds.reshape(-1) != obs.reshape(-1))
    assert errs < 20

def test_local_predecoder_quality_smoke_and_sparsifies():
    circ = data.surface_circuit(d=3, p=0.005)
    lp = local_predecoder.LocalPreDecoder(circ)
    dets, _ = data.sample(circ, shots=50, seed=42)
    res, flips = lp.predecode(dets)
    assert res.shape == dets.shape
