"""Integration tests for building the per-model mapping NetCDF product.

Uses small synthetic NetCDF files (not real TIPMIP data) to exercise the
provenance -> baseline -> mapping pipeline end to end, in particular the
out-of-span-branch-year regression covered by the NorESM2-LM case.
"""

import cftime
import numpy as np
import pytest
import xarray as xr

from tipmip_gwl.product import NotMappable, build_mapping_dataset

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


def _branch_time_in_parent(branch_year: int, parent_units: str) -> float:
    date = cftime.DatetimeNoLeap(branch_year, 1, 1)
    return cftime.date2num(date, units=parent_units, calendar=CALENDAR)


@pytest.fixture
def pi_control_file(tmp_path):
    path = tmp_path / "pi.nc"
    _write_monthly_tas(path, start_year=1851, n_years=250)  # 1851-2100
    return path


def test_branch_year_outside_picontrol_span_still_maps(tmp_path, pi_control_file):
    # Mirrors NorESM2-LM: decoded branch year 1600 predates the staged control
    # (1851-2100). Under the full-piControl-mean baseline this must map, not
    # raise NotMappable, and the out-of-span condition should surface as a
    # warning on the output dataset.
    parent_units = "days since 0001-01-01"
    branch_year = 1600
    ru_path = tmp_path / "ru.nc"
    _write_monthly_tas(
        ru_path,
        start_year=branch_year,
        n_years=50,
        trend_per_year=0.02,
        attrs={
            "source_id": "NorESM2-LM-like",
            "experiment_id": "esm-up2p0",
            "branch_method": "standard",
            "branch_time_in_parent": _branch_time_in_parent(branch_year, parent_units),
            "parent_time_units": parent_units,
            "parent_source_id": "NorESM2-LM-like",
            "parent_experiment_id": "esm-piControl",
        },
    )

    out = build_mapping_dataset("NorESM2-LM-like", ru_path, pi_control_file)

    assert out.attrs["baseline_method"] == "full_piControl_mean"
    assert "mapping_warnings" in out.attrs
    assert "outside staged piControl span" in out.attrs["mapping_warnings"]
    assert np.isfinite(out["baseline_gmsat"].values)
    assert np.isfinite(out["max_gwl_reached"].values)


def test_missing_picontrol_raises_not_mappable(tmp_path):
    ru_path = tmp_path / "ru.nc"
    _write_monthly_tas(ru_path, start_year=1850, n_years=10)
    with pytest.raises(NotMappable, match="no piControl"):
        build_mapping_dataset("SOME-MODEL", ru_path, pi_path=None)


def test_undecodable_branch_year_raises_not_mappable(tmp_path, pi_control_file):
    # No branch_time_in_parent/parent_time_units at all -> branch year cannot be
    # decoded -> still a hard failure (this is the one case that must raise).
    ru_path = tmp_path / "ru.nc"
    _write_monthly_tas(ru_path, start_year=1900, n_years=10)
    with pytest.raises(NotMappable, match="branch year could not be decoded"):
        build_mapping_dataset("SOME-MODEL", ru_path, pi_control_file)


def test_clean_model_maps_without_warnings(tmp_path, pi_control_file):
    parent_units = "days since 0001-01-01"
    branch_year = 1950  # inside the 1851-2100 control span
    ru_path = tmp_path / "ru.nc"
    _write_monthly_tas(
        ru_path,
        start_year=branch_year,
        n_years=50,
        trend_per_year=0.02,
        attrs={
            "source_id": "CLEAN-ESM",
            "experiment_id": "esm-up2p0",
            "branch_method": "standard",
            "branch_time_in_parent": _branch_time_in_parent(branch_year, parent_units),
            "parent_time_units": parent_units,
        },
    )

    out = build_mapping_dataset("CLEAN-ESM", ru_path, pi_control_file)
    assert "mapping_warnings" not in out.attrs
    assert int(out["branch_year"].values) == branch_year
