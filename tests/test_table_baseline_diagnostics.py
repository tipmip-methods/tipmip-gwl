"""Table A1 helpers: branch-window column must not mirror full-mean fallback."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PAPER_DIR = Path(__file__).resolve().parents[1] / "paper"
sys.path.insert(0, str(PAPER_DIR))

from helper_diagnostics import ModelDiag  # noqa: E402
from table_baseline_diagnostics import _branch_window_reference  # noqa: E402


def _diag(*, method: str, reference: float = 287.0) -> ModelDiag:
    return ModelDiag(
        model="test",
        branch_year=None,
        branch_known=None,
        baseline_method=method,
        pi_reference=reference,
        pi_reference_full=reference,
        pi_drift=0.0,
        max_gwl=4.0,
        monotonization_max=0.0,
        parent="",
    )


def test_branch_window_reference_returns_value_for_window_methods():
    d = _diag(method="branch_window_31yr", reference=286.95)
    assert _branch_window_reference(d) == 286.95
    d_trailing = _diag(method="branch_window_31yr_trailing", reference=287.1)
    assert _branch_window_reference(d_trailing) == 287.1


def test_branch_window_reference_none_when_baseline_fell_back_to_full_mean():
    ref = 287.603
    for method in ("full_piControl_mean", "full_piControl_mean_no_branch_year"):
        d = _diag(method=method, reference=ref)
        assert _branch_window_reference(d) is None
