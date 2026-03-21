"""Stim circuit-level surface-code data and detector-error-model matrices."""
from __future__ import annotations

import numpy as np
import stim

def surface_circuit(d: int, p: float, rounds: int | None = None) -> stim.Circuit:
    return stim.Circuit.generated(
        "surface_code:rotated_memory_z",
        distance=d,
        rounds=rounds or d,
        after_clifford_depolarization=p,
        after_reset_flip_probability=p,
        before_measure_flip_probability=p,
        before_round_data_depolarization=p,
    )

def sample(circuit: stim.Circuit, shots: int, seed: int = 0):
    """Returns (detectors uint8 [shots, n_det], observables uint8 [shots, n_obs])."""
    s = circuit.compile_detector_sampler(seed=seed)
    dets, obs = s.sample(shots, separate_observables=True)
    return dets.astype(np.uint8), obs.astype(np.uint8)
