"""Tests for provenance / branch-year decoding and the piControl baseline."""

import numpy as np
import pytest

from tipmip_gwl.baseline import (
    BranchInfo,
    branch_year_from_attrs,
    compute_baseline,
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


def test_resolve_branch_year_raises_when_undecoded():
    bi = BranchInfo(year=None, note="missing branch_time_in_parent/parent_time_units")
    with pytest.raises(ValueError):
        resolve_branch_year(bi, "SOME-MODEL")


def test_resolve_branch_year_out_of_span_warns_not_raises():
    # Regression test: under the full-piControl-mean baseline, a branch year
    # outside the staged control span (e.g. NorESM2-LM: branch 1600, control
    # 1851-2100) must NOT block mapping -- it is a warning only.
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


def test_compute_baseline_matches_mapping_picontrol_reference():
    years = np.arange(0, 500)
    rng = np.random.default_rng(0)
    vals = 286.5 + 0.05 * rng.standard_normal(years.size)
    base = compute_baseline(years, vals)
    assert base.method == "full_piControl_mean"
    assert base.reference == pytest.approx(
        picontrol_reference(years, vals, branch_year=None), abs=1e-9
    )
    assert base.n_years == years.size
    assert base.detrended is False


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
