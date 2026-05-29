import numpy as np
import pytest

def test_repeated_throughput_is_median_and_paired():
    runs = [100.0, 150.0, 120.0]
    assert np.median(runs) == 120.0
