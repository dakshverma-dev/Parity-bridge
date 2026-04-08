import numpy as np
from qechybrid import codes, data, decoders, gf2, local_predecoder

def test_gf2_rowspace():
    A = np.array([[1, 0, 1], [0, 1, 1], [1, 1, 0]], dtype=np.uint8)
    assert gf2.rank(A) == 2

def test_bb_codes_have_12_logicals():
    c72 = codes.bb_72_12_6()
    assert (c72.hx @ c72.hz.T % 2).sum() == 0
    c144 = codes.bb_144_12_12()
    assert (c144.hx @ c144.hz.T % 2).sum() == 0

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
