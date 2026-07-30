"""Tests for included ensemble validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tipmip_gwl.build import write_products
from tipmip_gwl.ensemble import (
    INCLUDED_MODELS,
    MissingEnsembleDataError,
    require_discovered,
)

PAPER_DIR = Path(__file__).resolve().parents[1] / "paper"
sys.path.insert(0, str(PAPER_DIR))
from helper_mlotst_remap import bundled_models  # noqa: E402
from test_product import _write_monthly_tas


def _gmstmon_path(directory: Path, model: str, exp: str) -> Path:
    return directory / f"tas_Amon_{model}_{exp}_r1i1p1f1_gn_gmstmon.nc"


def test_included_models_is_sorted_tier1():
    assert len(INCLUDED_MODELS) == 8
    assert INCLUDED_MODELS == tuple(sorted(INCLUDED_MODELS))


def test_required_gmstmon_experiments():
    from tipmip_gwl.ensemble import REQUIRED_GMSTMON_EXPERIMENTS

    assert len(REQUIRED_GMSTMON_EXPERIMENTS) == 4
    assert "esm-up2p0" in REQUIRED_GMSTMON_EXPERIMENTS
    assert "esm-piControl" in REQUIRED_GMSTMON_EXPERIMENTS


def test_require_discovered_raises_on_missing():
    with pytest.raises(MissingEnsembleDataError, match="Missing ramp-up"):
        require_discovered(
            ("GFDL-ESM2M", "TrialModel"),
            {"GFDL-ESM2M": Path("a.nc")},
            label="ramp-up",
        )


def test_bundled_models_raises_if_included_missing():
    up = {m: object() for m in INCLUDED_MODELS}
    dn = {m: object() for m in INCLUDED_MODELS[:-1]}
    with pytest.raises(MissingEnsembleDataError, match="UKESM1-2-LL"):
        bundled_models(up, dn)


def test_write_products_subset_ignores_extra_staged_models(tmp_path):
    """Trial models in staging are ignored when ``models`` is overridden."""
    ru_dir = tmp_path / "up"
    pi_dir = tmp_path / "pi"
    out_dir = tmp_path / "mapping"
    ru_dir.mkdir()
    pi_dir.mkdir()

    for model in ("GFDL-ESM2M", "TrialModel"):
        _write_monthly_tas(
            _gmstmon_path(ru_dir, model, "esm-up2p0"), start_year=2000, n_years=30
        )
        _write_monthly_tas(
            _gmstmon_path(pi_dir, model, "esm-piControl"), start_year=1851, n_years=250
        )

    written, skipped = write_products(ru_dir, pi_dir, out_dir, models=("GFDL-ESM2M",))
    assert skipped == []
    assert len(written) == 1
    assert written[0][0] == "GFDL-ESM2M"
    assert len(list(out_dir.glob("gwlmap_*.nc"))) == 1


def test_write_products_full_ensemble_raises_if_any_missing(tmp_path):
    ru_dir = tmp_path / "up"
    pi_dir = tmp_path / "pi"
    ru_dir.mkdir()
    pi_dir.mkdir()
    _write_monthly_tas(
        _gmstmon_path(ru_dir, "GFDL-ESM2M", "esm-up2p0"), start_year=2000, n_years=30
    )
    _write_monthly_tas(
        _gmstmon_path(pi_dir, "GFDL-ESM2M", "esm-piControl"),
        start_year=1851,
        n_years=250,
    )

    with pytest.raises(MissingEnsembleDataError, match="Missing ramp-up"):
        write_products(ru_dir, pi_dir, tmp_path / "mapping")
