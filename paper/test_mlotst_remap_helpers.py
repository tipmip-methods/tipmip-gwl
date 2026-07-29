"""Tests for paper mlotst regional-mean helpers."""

import numpy as np
import pytest
import xarray as xr

from mlotst_remap_helpers import (
    area_weighted_regional_mean,
    lon_to_180,
    rect_region_mask,
    smooth_annual_series,
)


def test_lon_to_180_wraps_0_360_grid():
    assert lon_to_180(290.0) == pytest.approx(-70.0)
    assert lon_to_180(350.0) == pytest.approx(-10.0)


def test_rect_region_mask_on_2d_curvilinear_grid():
    lat = xr.DataArray(
        np.array([[50.0, 50.0], [55.0, 55.0]]),
        dims=("y", "x"),
    )
    lon = xr.DataArray(
        np.array([[300.0, 340.0], [300.0, 340.0]]),  # 300=-60, 340=-20
        dims=("y", "x"),
    )
    mask = rect_region_mask(
        lat, lon, lon_min=-70.0, lon_max=-10.0, lat_min=45.0, lat_max=60.0
    )
    assert mask.shape == (2, 2)
    assert bool(mask[0, 0]) is True
    assert bool(mask[0, 1]) is True
    assert bool(mask[1, 0]) is True
    assert bool(mask[1, 1]) is True


def test_rect_region_mask_on_regular_lat_lon_grid():
    lat = xr.DataArray(np.array([40.0, 50.0, 60.0]), dims=("lat",))
    lon = xr.DataArray(np.array([300.0, 340.0]), dims=("lon",))  # -60, -20
    lat2d, lon2d = lat.broadcast_like(
        xr.DataArray(np.zeros((3, 2)), dims=("lat", "lon"))
    ), lon.broadcast_like(xr.DataArray(np.zeros((3, 2)), dims=("lat", "lon")))
    mask = rect_region_mask(
        lat2d, lon2d, lon_min=-70.0, lon_max=-10.0, lat_min=45.0, lat_max=60.0
    )
    assert mask.shape == (3, 2)
    assert bool(mask[0, 0]) is False  # 40N
    assert bool(mask[1, 0]) is True   # 50N, -60E
    assert bool(mask[2, 1]) is True   # 60N, -20E


def test_rect_region_mask_excludes_outside_box():
    lat = xr.DataArray(np.array([[30.0, 50.0]]), dims=("y", "x"))
    lon = xr.DataArray(np.array([[300.0, 300.0]]), dims=("y", "x"))
    mask = rect_region_mask(
        lat, lon, lon_min=-70.0, lon_max=-10.0, lat_min=45.0, lat_max=60.0
    )
    assert bool(mask[0, 0]) is False
    assert bool(mask[0, 1]) is True


def test_smooth_annual_series_reduces_noise():
    rng = np.random.default_rng(0)
    signal = np.sin(np.linspace(0, 4 * np.pi, 80))
    noisy = signal + 0.4 * rng.standard_normal(80)
    smooth = smooth_annual_series(noisy, sigma_yr=6.0)
    assert smooth.shape == noisy.shape
    assert np.std(smooth - signal) < np.std(noisy - signal)


def test_area_weighted_regional_mean_excludes_land_cells():
    lat = xr.DataArray(np.array([[50.0, 50.0]]), dims=("y", "x"))
    lon = xr.DataArray(np.array([[300.0, 340.0]]), dims=("y", "x"))
    da = xr.DataArray(
        np.array([[[100.0, 0.0]]]),
        dims=("time", "y", "x"),
        coords={"time": [2000.0]},
    )
    out = area_weighted_regional_mean(
        da, lat, lon, lon_min=-70.0, lon_max=-10.0, lat_min=45.0, lat_max=60.0
    )
    assert out.shape == (1,)
    assert out[0] == pytest.approx(100.0)
