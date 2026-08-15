import pytest
from release_app.comparison import compare_runs

def test_incompatible_workload():
    with pytest.raises(ValueError):
        compare_runs({"manifest": {"family": "surface"}}, {"manifest": {"family": "qldpc"}})
