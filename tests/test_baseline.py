"""Tests for provenance / branch-year decoding and the piControl baseline."""

import numpy as np
import pytest

from tipmip_gwl.baseline import (
    BranchInfo,
    branch_year_from_attrs,
    compute_baseline,
    branch_window_reference,
    provenance_warnings,
    resolve_branch_year,
)
from tipmip_gwl.mapping import picontrol_reference


def test_branch_year_from_attrs_decodes_noleap_calendar():
    # 1850-01-01 + 100*365 days on a noleap calendar lands exactly on 1950-01-01.
    attrs = {
        "branch_time_in_parent": 100 * 365.0,
        "parent_time_units": "days since 1850-01-01",
    }
    info = branch_year_from_attrs(attrs, calendar="noleap")
    assert info.year == 1950
    assert info.at_parent_start is False


def test_branch_year_from_attrs_day_zero_flags_parent_start():
    attrs = {
        "branch_time_in_parent": 0.0,
        "parent_time_units": "days since 1850-01-01",
    }
    info = branch_year_from_attrs(attrs, calendar="noleap")
    assert info.year == 1850
    assert info.at_parent_start is True
    assert "day 0" in info.note


def test_branch_year_from_attrs_missing_metadata_leaves_year_none():
    info = branch_year_from_attrs({})
    assert info.year is None
    assert "missing" in info.note


def test_resolve_branch_year_never_raises_no_parent_declared():
    # Regression test: UKESM1-2-LL-like case (no parent metadata at all, e.g. a
    # run from a different project/experiment). Per explicit confirmation this
    # data is usable, so there are no hard gates beyond "no piControl file at
    # all" (enforced elsewhere) -- this must warn, not raise.
    bi = BranchInfo(year=None, note="missing branch_time_in_parent/parent_time_units")
    branch, warns = resolve_branch_year(bi, "SOME-MODEL")
    assert branch is None
    assert any("no parent run declared" in w for w in warns)


def test_resolve_branch_year_warns_when_parent_declared_but_year_undecodable():
    bi = BranchInfo(
        year=None,
        parent_source_id="SOME-MODEL",
        parent_experiment_id="esm-piControl",
        note="cftime decode failed: bad units",
    )
    branch, warns = resolve_branch_year(bi, "SOME-MODEL")
    assert branch is None
    assert any("branch year could not be decoded" in w for w in warns)
    assert not any("no parent run declared" in w for w in warns)


def test_resolve_branch_year_out_of_span_warns_not_raises():
    # NorESM2-LM: branch 1600, control 1851-2100. Must warn and fall back to
    # full piControl mean at compute_baseline time, not raise here.
    bi = BranchInfo(year=1600)
    pi_years = np.arange(1851, 2101)
    branch, warns = resolve_branch_year(bi, "NorESM2-LM", pi_years=pi_years)
    assert branch == 1600
    assert any("outside staged piControl span" in w for w in warns)


def test_resolve_branch_year_in_span_has_no_warning():
    bi = BranchInfo(year=1950)
    pi_years = np.arange(1850, 2101)
    branch, warns = resolve_branch_year(bi, "SOME-MODEL", pi_years=pi_years)
    assert branch == 1950
    assert warns == []


def test_resolve_branch_year_known_mismatch_warns():
    bi = BranchInfo(year=1962)  # KNOWN_BRANCH_YEARS["GFDL-ESM2M"] == 1961
    branch, warns = resolve_branch_year(bi, "GFDL-ESM2M")
    assert branch == 1962
    assert any("mismatch" in w for w in warns)


def test_provenance_warnings_flags_wrong_experiment_and_no_parent():
    attrs = {"experiment_id": "esm-piControl", "branch_method": "no parent"}
    warns = provenance_warnings(attrs, expect_experiment="esm-up2p0")
    assert any("experiment_id" in w for w in warns)
    assert any("no parent" in w for w in warns)


def test_provenance_warnings_clean_attrs_pass():
    attrs = {
        "experiment_id": "esm-up2p0",
        "branch_method": "standard",
        "branch_time_in_parent": 0.0,
        "parent_time_units": "days since 1850-01-01",
    }
    assert provenance_warnings(attrs) == []


def test_compute_baseline_uses_branch_window_when_in_span():
    years = np.arange(1850, 2101)
    vals = 286.5 + 0.001 * (years - years.mean())
    branch = 1950
    base = compute_baseline(years, vals, branch_year=branch)
    assert base.method == "branch_window_31yr"
    assert base.reference == pytest.approx(
        branch_window_reference(years, vals, branch), abs=1e-9
    )
    assert base.reference != pytest.approx(
        picontrol_reference(years, vals, branch_year=None), abs=1e-6
    )


def test_compute_baseline_trailing_window_at_picontrol_start():
    years = np.arange(271, 771)
    vals = np.full(years.size, 287.7)
    base = compute_baseline(years, vals, branch_year=271)
    assert base.method == "branch_window_31yr_trailing"
    assert base.reference == pytest.approx(287.7, abs=1e-9)


def test_compute_baseline_out_of_span_uses_full_mean():
    years = np.arange(1851, 2101)
    vals = np.full(years.size, 287.6)
    base = compute_baseline(years, vals, branch_year=1600)
    assert base.method == "full_piControl_mean"
    assert base.reference == pytest.approx(
        picontrol_reference(years, vals, branch_year=None), abs=1e-9
    )


def test_compute_baseline_flags_missing_branch_year():
    years = np.arange(0, 500)
    vals = np.full(years.size, 286.5)
    base = compute_baseline(years, vals, branch_year=None)
    assert base.method == "full_piControl_mean_no_branch_year"


def test_compute_baseline_detrend_requires_branch_year():
    years = np.arange(0, 100)
    vals = np.full(100, 286.5)
    with pytest.raises(ValueError):
        compute_baseline(years, vals, branch_year=None, detrend=True)


def test_compute_baseline_reports_drift():
    years = np.arange(0, 1000, dtype=float)
    vals = 286.0 + 0.002 * years  # 0.2 degC/century
    base = compute_baseline(years, vals)
    assert base.drift_degC_per_century == pytest.approx(0.2, abs=1e-6)
