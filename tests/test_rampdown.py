"""Integration tests for building the per-model ramp-down mapping NetCDF product.

Uses small synthetic NetCDF files (not real TIPMIP data) to exercise the
provenance -> baseline -> mapping pipeline for the ramp-down leg, in
particular that its parent-chain metadata (pointing at the zero-emission
hold run, not piControl) is handled as informational only.
"""

import numpy as np
import pytest
import xarray as xr

from tipmip_gwl.product import NotMappable
from tipmip_gwl.rampdown import build_rampdown_mapping_dataset, write_rampdown_mapping

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


def test_rampdown_parent_is_hold_run_not_picontrol(tmp_path, pi_control_file):
    # Normal ramp-down case: parent_experiment_id is the zero-emission hold
    # run (e.g. esm-up2p0-gwl2p0), not piControl. This must map (not raise)
    # and should carry an informational warning, not a fatal error.
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,  # 286.5 + 2.0 branch anomaly
        trend_per_year=-0.02,
        attrs={
            "source_id": "RAMPDOWN-ESM",
            "experiment_id": "esm-up2p0-gwl2p0-50y-dn2p0",
            "branch_method": "standard",
            "parent_source_id": "RAMPDOWN-ESM",
            "parent_experiment_id": "esm-up2p0-gwl2p0",
            "branch_time_in_parent": 18262.0,
            "parent_time_units": "days since 1850-01-01",
        },
    )

    out = build_rampdown_mapping_dataset("RAMPDOWN-ESM", dn_path, pi_control_file)

    assert out.attrs["leg"] == "ramp-down"
    assert out.attrs["baseline_method"] == "full_piControl_mean_no_branch_year"
    assert "mapping_warnings" in out.attrs
    assert "esm-up2p0-gwl2p0" in out.attrs["mapping_warnings"]
    assert np.isfinite(out["baseline_gmsat"].values)
    assert np.isfinite(out["min_gwl_reached"].values)
    # the axis must cool, not warm
    assert out["min_gwl_reached"].values <= out["gwl_at_branch"].values


def test_rampdown_axis_is_monotone_nonincreasing(tmp_path, pi_control_file):
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,
        trend_per_year=-0.02,
        attrs={
            "source_id": "RAMPDOWN-ESM",
            "experiment_id": "esm-up2p0-gwl2p0-50y-dn2p0",
            "parent_experiment_id": "esm-up2p0-gwl2p0",
        },
    )
    out = build_rampdown_mapping_dataset("RAMPDOWN-ESM", dn_path, pi_control_file)
    gwl_axis = out["gwl_axis"].values
    assert np.all(np.diff(gwl_axis) <= 1e-9)


def test_rampdown_warns_when_model_exceeds_configured_grid(tmp_path, pi_control_file):
    # A model that cools well past the default grid's -1.5 degC floor should
    # get a loud warning, not a silently truncated common-grid product.
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,  # +2.0 degC branch anomaly
        trend_per_year=-0.05,  # cools well past -1.5 degC over 120 years
        attrs={
            "source_id": "DEEP-COOLER",
            "experiment_id": "esm-up2p0-gwl2p0-50y-dn2p0",
            "parent_experiment_id": "esm-up2p0-gwl2p0",
        },
    )
    out = build_rampdown_mapping_dataset("DEEP-COOLER", dn_path, pi_control_file)
    assert "mapping_warnings" in out.attrs
    assert "below the configured T_grid minimum" in out.attrs["mapping_warnings"]


def test_rampdown_no_warning_when_within_configured_grid(tmp_path, pi_control_file):
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,
        trend_per_year=-0.02,  # stays within the default -1.5..2.5 grid
        attrs={
            "source_id": "WITHIN-GRID",
            "experiment_id": "esm-up2p0-gwl2p0-50y-dn2p0",
            "parent_experiment_id": "esm-up2p0-gwl2p0",
        },
    )
    out = build_rampdown_mapping_dataset("WITHIN-GRID", dn_path, pi_control_file)
    assert "mapping_warnings" not in out.attrs or "T_grid" not in out.attrs.get(
        "mapping_warnings", ""
    )


def test_rampdown_missing_picontrol_raises_not_mappable(tmp_path):
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(dn_path, start_year=2000, n_years=10, trend_per_year=-0.02)
    with pytest.raises(NotMappable, match="no piControl"):
        build_rampdown_mapping_dataset("SOME-MODEL", dn_path, pi_path=None)


def test_rampdown_no_parent_declared_still_maps(tmp_path, pi_control_file):
    # Mirrors the UKESM ramp-down case: TerraFIRMA file, no parent linkage at
    # all. Must map, not raise -- the only hard gate is a missing piControl.
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=1994,
        n_years=10,
        mean=288.5,
        trend_per_year=-0.02,
        attrs={
            "source_id": "NO-PARENT-DN-MODEL",
            "experiment_id": "Dn-8GtC-50y-2p0",
            "branch_method": "no parent",
        },
    )
    out = build_rampdown_mapping_dataset("NO-PARENT-DN-MODEL", dn_path, pi_control_file)
    assert out.attrs["baseline_method"] == "full_piControl_mean_no_branch_year"
    assert "no parent run declared" in out.attrs["mapping_warnings"]
    assert np.isfinite(out["baseline_gmsat"].values)


def test_rampdown_uses_own_t_grid_by_default(tmp_path, pi_control_file):
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,
        trend_per_year=-0.02,
        attrs={
            "source_id": "RAMPDOWN-ESM",
            "experiment_id": "esm-up2p0-gwl2p0-50y-dn2p0",
            "parent_experiment_id": "esm-up2p0-gwl2p0",
        },
    )
    out = build_rampdown_mapping_dataset("RAMPDOWN-ESM", dn_path, pi_control_file)
    # default grid spans negative GWLs, unlike the ramp-up leg's 0-4 grid
    assert out["gwl"].values.min() < 0.0


def test_write_rampdown_mapping_filenames_by_experiment_id(tmp_path, pi_control_file):
    dn_path = tmp_path / "dn.nc"
    _write_monthly_tas(
        dn_path,
        start_year=2000,
        n_years=120,
        mean=288.5,
        trend_per_year=-0.02,
        attrs={
            "source_id": "NorESM2-LM",
            "experiment_id": "esm-up2p0-swl2p0-50y-dn2p0",
            "parent_experiment_id": "esm-up2p0-swl2p0",
        },
    )
    out = build_rampdown_mapping_dataset("NorESM2-LM", dn_path, pi_control_file)
    path = write_rampdown_mapping(out, tmp_path / "mapping_out")
    assert path.name == "gwlmap_NorESM2-LM_esm-up2p0-swl2p0-50y-dn2p0_v1.nc"
    assert path.exists()
