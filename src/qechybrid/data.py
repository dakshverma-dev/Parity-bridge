"""Stim circuit-level surface-code data and detector-error-model matrices."""
from __future__ import annotations

import stim

def surface_circuit(d: int, p: float, rounds: int | None = None) -> stim.Circuit:
    return stim.Circuit.generated("surface_code:rotated_memory_z", distance=d, rounds=rounds or d)
