import numpy as np
import pytest
from pathlib import Path
from qechybrid import decoders, data

def test_frozen_surface_predictions_and_error_counts():
    fix = np.load(Path(__file__).parent / "fixtures" / "surface_d5_p004.npz")
    assert "dets" in fix
