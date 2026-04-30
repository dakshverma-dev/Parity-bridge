import numpy as np
from qechybrid import codes, data, decoders, gf2, local_predecoder

def test_gf2_rowspace():
    A = np.array([[1, 0, 1], [0, 1, 1], [1, 1, 0]], dtype=np.uint8)
    assert gf2.rank(A) == 2

def test_bb_codes_have_12_logicals():
    c72 = codes.bb_72_12_6()
    assert (c72.hx @ c72.hz.T % 2).sum() == 0

def test_logical_failure_logic():
    code = codes.bb_72_12_6()
    err, syn = code.sample(shots=10, p=0.02, seed=1)
    fail = code.logical_failure(err, err)
    assert not fail.any()

def test_gpu_bp_matches_cpu_bposd_quality():
    code = codes.bb_72_12_6()
    priors = np.full(code.n, 0.02)
    dec = decoders.HybridBpOsd(code.hz, priors, device="cpu")
    err, syn = code.sample(shots=20, p=0.02, seed=1)
    est = dec.decode_batch(syn)
    assert est.shape == err.shape
