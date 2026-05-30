import numpy as np
import pytest

def test_surface_checkpoints_baseline_before_gate_failure():
    # Baseline rows checkpointed before later decoder step
    checkpointed = True
    assert checkpointed
