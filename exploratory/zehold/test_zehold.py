"""Integration tests for the zero-emission-hold ("ZE") mapping product.

Uses small synthetic NetCDF files (not real TIPMIP data). Unlike the ramp-up/
ramp-down products, this leg is never monotonized and ships no year_of_gwl or
common gwl grid -- these tests check that structural difference directly,
plus the provenance and drift-diagnostic behaviour specific to this leg.

Run from the repo root::

    pytest exploratory/zehold/test_zehold.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zehold import _parse_target_gwl, build_ze_mapping_dataset, write_ze_mapping
from tipmip_gwl.product import NotMappable

CALENDAR = "noleap"


def _write_monthly_tas(
    path, start_year, n_years, *, mean=286.5, trend_per_year=0.0, attrs=None
):
    n_months = n_years * 12
    time = xr.date_range(
        start=f"{start_year}-01-01",
        periods=n_months,
        freq="MS",
        calendar=CALENDAR,
        use_cftime=True,
    )
    rng = np.random.default_rng(abs(hash((str(path), start_year))) % (2**32))
    years_frac = np.arange(n_months) / 12.0
    tas = mean + trend_per_year * years_frac + 0.05 * rng.standard_normal(n_months)
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), tas.reshape(-1, 1, 1))},
        coords={"time": time, "lat": [0.0], "lon": [0.0]},
        attrs=attrs or {},
    )
    ds.to_netcdf(path)
    ds.close()


@pytest.fixture
def pi_control_file(tmp_path):
    path = tmp_path / "pi.nc"
    _write_monthly_tas(path, start_year=1851, n_years=250)  # 1851-2100
    return path


def test_parse_target_gwl_all_naming_conventions():
    cases = {
        "esm-up2p0-gwl2p0": 2.0,
        "esm-up2p0-gwl4p0": 4.0,
        "esm-up2p0-swl2p0": 2.0,
        "esm-up2p0-swl4p0": 4.0,
        "ZE-Up-2p0": 2.0,
        "ZE-Up-4p0": 4.0,
    }
    for exp_id, expected in cases.items():
        assert _parse_target_gwl(exp_id) == pytest.approx(expected)
    assert np.isnan(_parse_target_gwl("bogus-experiment"))


def test_zehold_no_monotonization_wander_is_preserved(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    n_years = 50
    years_frac = np.arange(n_years * 12) / 12.0
    wobble = np.where(years_frac < 25, years_frac * 0.02, (50 - years_frac) * 0.02)
    time = xr.date_range("2000-01-01", periods=n_years * 12, freq="MS", calendar=CALENDAR, use_cftime=True)
    tas = 288.5 + wobble
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), tas.reshape(-1, 1, 1))},
        coords={"time": time, "lat": [0.0], "lon": [0.0]},
        attrs={
            "source_id": "WOBBLE-ESM",
            "experiment_id": "esm-up2p0-gwl2p0",
            "parent_experiment_id": "esm-up2p0",
            "branch_method": "standard",
        },
    )
    ds.to_netcdf(ze_path)
    ds.close()

    out = build_ze_mapping_dataset("WOBBLE-ESM", ze_path, pi_control_file, window=11)
    gwl_axis = out["gwl_axis"].values
    assert not np.all(np.diff(gwl_axis) >= -1e-9)
    assert not np.all(np.diff(gwl_axis) <= 1e-9)
    assert "year_of_gwl" not in out
    assert "gwl" not in out.coords


def test_zehold_ships_no_inverse_or_common_grid(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=2000,
        n_years=50,
        mean=288.5,
        trend_per_year=0.0,
        attrs={
            "source_id": "FLAT-ESM",
            "experiment_id": "esm-up2p0-gwl2p0",
            "parent_experiment_id": "esm-up2p0",
        },
    )
    out = build_ze_mapping_dataset("FLAT-ESM", ze_path, pi_control_file)
    assert "year_of_gwl" not in out.data_vars
    assert "gwl" not in out.coords
    assert out.attrs["leg"] == "ze-hold"
    assert "hysteresis_note" in out.attrs


def test_zehold_net_drift_sign_and_magnitude(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=2000,
        n_years=50,
        mean=288.5,
        trend_per_year=0.01,
        attrs={
            "source_id": "WARMING-HOLD",
            "experiment_id": "esm-up2p0-gwl2p0",
            "parent_experiment_id": "esm-up2p0",
        },
    )
    out = build_ze_mapping_dataset("WARMING-HOLD", ze_path, pi_control_file, window=11)
    assert float(out["net_drift"].values) > 0
    assert float(out["target_gwl"].values) == pytest.approx(2.0)


def test_zehold_parent_is_rampup_not_flagged(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=2000,
        n_years=50,
        mean=288.5,
        attrs={
            "source_id": "NORMAL-ESM",
            "experiment_id": "esm-up2p0-gwl2p0",
            "branch_method": "standard",
            "parent_source_id": "NORMAL-ESM",
            "parent_experiment_id": "esm-up2p0",
            "branch_time_in_parent": 18262.0,
            "parent_time_units": "days since 1850-01-01",
        },
    )
    out = build_ze_mapping_dataset("NORMAL-ESM", ze_path, pi_control_file)
    assert "mapping_warnings" not in out.attrs
    assert np.isfinite(out["branch_year_in_parent"].values)


def test_zehold_unexpected_parent_is_flagged(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=2000,
        n_years=50,
        mean=288.5,
        attrs={
            "source_id": "NorESM2-LM-like",
            "experiment_id": "esm-up2p0-swl2p0",
            "branch_method": "branch-restart from year 1600-01-01 of piControl",
            "parent_source_id": "NorESM2-LM-like",
            "parent_experiment_id": "piControl",
            "branch_time_in_parent": 430335.0,
            "parent_time_units": "days since 0421-01-01",
        },
    )
    out = build_ze_mapping_dataset("NorESM2-LM-like", ze_path, pi_control_file)
    assert "mapping_warnings" in out.attrs
    assert "not esm-up2p0" in out.attrs["mapping_warnings"]


def test_zehold_no_parent_declared_still_maps(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=1994,
        n_years=50,
        mean=288.5,
        attrs={
            "source_id": "NO-PARENT-ZE-MODEL",
            "experiment_id": "ZE-Up-2p0",
            "branch_method": "no parent",
        },
    )
    out = build_ze_mapping_dataset("NO-PARENT-ZE-MODEL", ze_path, pi_control_file)
    assert "no parent run declared" in out.attrs["mapping_warnings"]
    assert np.isfinite(out["baseline_gmsat"].values)
    assert float(out["target_gwl"].values) == pytest.approx(2.0)


def test_zehold_missing_picontrol_raises_not_mappable(tmp_path):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(ze_path, start_year=2000, n_years=50)
    with pytest.raises(NotMappable, match="no piControl"):
        build_ze_mapping_dataset("SOME-MODEL", ze_path, pi_path=None)


def test_write_ze_mapping_filenames_by_experiment_id(tmp_path, pi_control_file):
    ze_path = tmp_path / "ze.nc"
    _write_monthly_tas(
        ze_path,
        start_year=2000,
        n_years=50,
        mean=288.5,
        attrs={
            "source_id": "NorESM2-LM",
            "experiment_id": "esm-up2p0-swl4p0",
            "parent_experiment_id": "esm-up2p0",
        },
    )
    out = build_ze_mapping_dataset("NorESM2-LM", ze_path, pi_control_file)
    path = write_ze_mapping(out, tmp_path / "mapping_out")
    assert path.name == "gwlmap_NorESM2-LM_esm-up2p0-swl4p0_v1.nc"
    assert path.exists()
