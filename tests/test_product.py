"""Integration tests for building the per-model mapping NetCDF product.

Uses small synthetic NetCDF files (not real TIPMIP data) to exercise the
provenance -> baseline -> mapping pipeline end to end, in particular the
out-of-span-branch-year regression covered by the NorESM2-LM case.
"""

import warnings

import cftime
import numpy as np
import pytest
import xarray as xr

from tipmip_gwl import LEG_RAMP_DOWN_2C, LEG_RAMP_DOWN_4C, LEG_RAMP_UP, load_mapping
from tipmip_gwl.build import build_mapping_dataset
from tipmip_gwl.product import (
    NotMappable,
    bundled_mapping_path,
    bundled_mappings_dir,
    list_models,
    resolve_mapping_path,
    relabel_to_gwl,
    resample_to_gwl,
)

from conftest import requires_mappings

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
    # (1851-2100). Mapping must proceed with a full-mean fallback baseline, and
    # the out-of-span condition should surface as a warning on the output dataset.
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


def test_no_parent_declared_still_maps(tmp_path, pi_control_file):
    # Regression test: UKESM1-2-LL-like case -- no branch_time_in_parent /
    # parent_time_units at all, no parent linkage declared. Per explicit
    # confirmation this data is usable; the only hard gate is a missing
    # piControl file (covered by test_missing_picontrol_raises_not_mappable),
    # so this must map, not raise.
    ru_path = tmp_path / "ru.nc"
    _write_monthly_tas(
        ru_path,
        start_year=1900,
        n_years=10,
        attrs={
            "source_id": "NO-PARENT-MODEL",
            "experiment_id": "Up-8GtC",
            "branch_method": "no parent",
        },
    )
    out = build_mapping_dataset("NO-PARENT-MODEL", ru_path, pi_control_file)
    assert out.attrs["baseline_method"] == "full_piControl_mean_no_branch_year"
    assert np.isnan(out["branch_year"].values)
    assert "no parent run declared" in out.attrs["mapping_warnings"]
    assert np.isfinite(out["baseline_gmsat"].values)


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
    assert out.attrs["baseline_method"] == "branch_window_31yr"


@requires_mappings
def test_bundled_mappings_dir_exists():
    root = bundled_mappings_dir()
    assert root.is_dir()
    assert any(root.glob("gwlmap_*.nc"))


@requires_mappings
def test_list_models_matches_rampup_v1_files():
    root = bundled_mappings_dir()
    n_files = len(list(root.glob("gwlmap_*_esm-up2p0_v1.nc")))
    models = list_models()
    assert len(models) == n_files
    assert n_files >= 8
    assert "GFDL-ESM2M" in models


@requires_mappings
def test_bundled_mapping_path_resolves():
    path = bundled_mapping_path("GFDL-ESM2M")
    assert path.name == "gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc"
    assert path.is_file()


@requires_mappings
def test_bundled_mapping_path_unknown_model():
    with pytest.raises(FileNotFoundError, match="no mapping"):
        bundled_mapping_path("Not-A-Model")


@requires_mappings
def test_load_mapping_returns_in_memory_dataset():
    ds = load_mapping("GFDL-ESM2M")
    assert isinstance(ds, xr.Dataset)
    assert "year_of_gwl" in ds
    assert "gwl_axis" in ds
    assert ds.attrs.get("mapping_version") == "v1"
    assert str(ds.attrs.get("leg", "ramp-up")) == "ramp-up"


@requires_mappings
def test_load_mapping_custom_path(tmp_path):
    src = bundled_mapping_path("GFDL-ESM2M")
    custom = tmp_path / src.name
    custom.write_bytes(src.read_bytes())
    ds = load_mapping("GFDL-ESM2M", path=custom)
    assert ds.attrs["source_id"] == load_mapping("GFDL-ESM2M").attrs["source_id"]


@requires_mappings
def test_load_mapping_ramp_down_leg(tmp_path):
    up = bundled_mapping_path("GFDL-ESM2M")
    dn_name = "gwlmap_GFDL-ESM2M_esm-up2p0-gwl2p0-50y-dn2p0_v1.nc"
    dn_path = tmp_path / dn_name
    dn_path.write_bytes(up.read_bytes())
    ds = load_mapping("GFDL-ESM2M", leg=LEG_RAMP_DOWN_2C, mapping_dir=tmp_path)
    assert ds.attrs.get("source_id") == load_mapping("GFDL-ESM2M").attrs["source_id"]


@requires_mappings
def test_load_mapping_bundled_ramp_down_leg():
    ds = load_mapping("GFDL-ESM2M", leg=LEG_RAMP_DOWN_2C)
    assert "year_of_gwl" in ds
    assert str(ds.attrs.get("leg", "")) == "ramp-down"


@requires_mappings
def test_load_mapping_bundled_ukesm_prefers_standard_dn2c():
    path = resolve_mapping_path("UKESM1-2-LL", leg=LEG_RAMP_DOWN_2C)
    assert path.name == "gwlmap_UKESM1-2-LL_esm-up2p0-gwl2p0-50y-dn2p0_v1.nc"


@requires_mappings
def test_list_models_bundled_ramp_down():
    models = list_models(leg=LEG_RAMP_DOWN_2C)
    assert len(models) >= 8
    assert "GFDL-ESM2M" in models


@requires_mappings
def test_load_mapping_noresm_swl_dn_leg(tmp_path):
    up = bundled_mapping_path("GFDL-ESM2M")
    dn_name = "gwlmap_NorESM2-LM_esm-up2p0-swl2p0-50y-dn2p0_v1.nc"
    (tmp_path / dn_name).write_bytes(up.read_bytes())
    models = list_models(leg=LEG_RAMP_DOWN_2C, mapping_dir=tmp_path)
    assert models == ["NorESM2-LM"]
    ds = load_mapping("NorESM2-LM", leg=LEG_RAMP_DOWN_2C, mapping_dir=tmp_path)
    assert "year_of_gwl" in ds


def test_resolve_mapping_path_unknown_leg():
    with pytest.raises(ValueError, match="unknown leg"):
        resolve_mapping_path("GFDL-ESM2M", leg="sideways")


def test_resample_to_gwl_uses_mapping_gwl_grid():
    gwl = np.arange(-1.0, 2.0001, 0.5)
    years = 2000.0 + gwl * 10.0
    mapping_ds = xr.Dataset(
        {"year_of_gwl": ("gwl", years.astype(float))},
        coords={"gwl": gwl.astype(float)},
    )
    diag_years = np.arange(1990, 2021)
    diagnostic = xr.DataArray(
        diag_years.astype(float) - 1900.0,
        dims="year",
        coords={"year": diag_years},
        name="diag",
    )
    out = resample_to_gwl(mapping_ds, diagnostic)
    np.testing.assert_allclose(out["gwl"].values, gwl)
    assert float(out.sel(gwl=0.0)) == pytest.approx(100.0)


def test_resample_to_gwl_narrows_within_stored_range_silently():
    gwl = np.arange(-1.0, 2.0001, 0.5)
    years = 2000.0 + gwl * 10.0
    mapping_ds = xr.Dataset(
        {"year_of_gwl": ("gwl", years.astype(float))},
        coords={"gwl": gwl.astype(float)},
    )
    diag_years = np.arange(1990, 2021)
    diagnostic = xr.DataArray(
        diag_years.astype(float) - 1900.0,
        dims="year",
        coords={"year": diag_years},
        name="diag",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = resample_to_gwl(mapping_ds, diagnostic, gwl_min=0.0, gwl_max=1.0)
    assert float(out["gwl"].min()) >= 0.0
    assert float(out["gwl"].max()) <= 1.0


def test_resample_to_gwl_clamps_and_warns_beyond_stored_range():
    gwl = np.arange(-1.0, 2.0001, 0.5)
    years = 2000.0 + gwl * 10.0
    mapping_ds = xr.Dataset(
        {"year_of_gwl": ("gwl", years.astype(float))},
        coords={"gwl": gwl.astype(float)},
    )
    diag_years = np.arange(1990, 2021)
    diagnostic = xr.DataArray(
        diag_years.astype(float) - 1900.0,
        dims="year",
        coords={"year": diag_years},
        name="diag",
    )
    with pytest.warns(UserWarning, match="gwl_max=8 is above"):
        out = resample_to_gwl(mapping_ds, diagnostic, gwl_max=8.0)
    assert float(out["gwl"].max()) == pytest.approx(2.0)

    with pytest.warns(UserWarning, match="gwl_min=-5 is below"):
        out = resample_to_gwl(mapping_ds, diagnostic, gwl_min=-5.0)
    assert float(out["gwl"].min()) == pytest.approx(-1.0)


def _synthetic_forward_mapping():
    years = np.arange(2000.0, 2011.0)
    return xr.Dataset(
        {"gwl_axis": ("year", np.linspace(0.0, 2.0, years.size))},
        coords={"year": years},
    )


def _numeric_year_diagnostic():
    years = np.arange(2000.0, 2011.0)
    return xr.DataArray(
        years - 2000.0,
        dims="time",
        coords={"time": years},
        name="diag",
    )


def test_relabel_to_gwl_accepts_numeric_calendar_years():
    out = relabel_to_gwl(_synthetic_forward_mapping(), _numeric_year_diagnostic(), year_dim="time")
    assert out.dims == ("gwl",)
    assert out.sizes["gwl"] == 11
    assert float(out["gwl"].max()) == pytest.approx(2.0)


def test_relabel_to_gwl_rejects_datetime64_time():
    times = np.array(["2000-01-01", "2001-01-01", "2002-01-01"], dtype="datetime64[ns]")
    diagnostic = xr.DataArray(
        [0.0, 1.0, 2.0],
        dims="time",
        coords={"time": times},
        name="diag",
    )
    with pytest.raises(TypeError, match="numeric coordinate"):
        relabel_to_gwl(_synthetic_forward_mapping(), diagnostic, year_dim="time")


def test_relabel_to_gwl_rejects_cftime_time():
    times = [
        cftime.DatetimeNoLeap(2000, 1, 1),
        cftime.DatetimeNoLeap(2001, 1, 1),
        cftime.DatetimeNoLeap(2002, 1, 1),
    ]
    diagnostic = xr.DataArray(
        [0.0, 1.0, 2.0],
        dims="time",
        coords={"time": times},
        name="diag",
    )
    with pytest.raises(TypeError, match="numeric coordinate"):
        relabel_to_gwl(_synthetic_forward_mapping(), diagnostic, year_dim="time")


def test_resample_to_gwl_rejects_datetime64_time():
    gwl = np.array([0.0, 1.0, 2.0])
    years = np.array([2000.0, 2005.0, 2010.0])
    mapping_ds = xr.Dataset(
        {"year_of_gwl": ("gwl", years)},
        coords={"gwl": gwl},
    )
    times = np.array(["2000-01-01", "2005-01-01", "2010-01-01"], dtype="datetime64[ns]")
    diagnostic = xr.DataArray(
        [0.0, 1.0, 2.0],
        dims="time",
        coords={"time": times},
        name="diag",
    )
    with pytest.raises(TypeError, match="numeric coordinate"):
        resample_to_gwl(mapping_ds, diagnostic, year_dim="time")
