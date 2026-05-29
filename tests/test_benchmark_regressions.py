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

def test_cpu_pipeline_never_synchronizes_cuda(monkeypatch):
    called = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *a, **kw: called.append(True))
    timing.sync("cpu")
    assert len(called) == 0

def test_cuda_timer_synchronizes_the_selected_device(monkeypatch):
    called = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda dev: called.append(dev))
    timing.sync("cuda:0")
    assert called == ["cuda:0"]
