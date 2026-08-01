"""Regional diagnostic time series for hysteresis figures (SPG mlotst, polar sivol)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter1d

SPG_LON_MIN = -70.0
SPG_LON_MAX = -10.0
SPG_LAT_MIN = 45.0
SPG_LAT_MAX = 60.0
SPG_MLOTST_YLABEL = "SPG regional-mean annual-max mixed-layer depth (m)"

ARCTIC_LAT_MIN = 60.0
ARCTIC_LAT_MAX = 90.0
ANTARCTIC_LAT_MIN = -90.0
ANTARCTIC_LAT_MAX = -50.0

GAUSSIAN_SIGMA_YR = 6.0


def lat_lon_fields(ds: xr.Dataset, da: xr.DataArray) -> tuple[xr.DataArray, xr.DataArray]:
    """Return (lat, lon) arrays broadcast-compatible with ``da``'s spatial dims."""
    lat_candidates = ("latitude", "lat", "nav_lat", "TLAT")
    lon_candidates = ("longitude", "lon", "nav_lon", "TLONG")
    lat = lon = None
    for name in lat_candidates:
        if name in ds.variables:
            lat = ds[name]
            break
    for name in lon_candidates:
        if name in ds.variables:
            lon = ds[name]
            break
    if lat is None or lon is None:
        raise KeyError(f"no lat/lon fields found among {list(ds.variables)}")
    return lat, lon


def _lon_to_180(lon: xr.DataArray) -> xr.DataArray:
    """Express longitudes on [-180, 180) for box masks."""
    return (((lon + 180) % 360) - 180)


def rect_region_mask(
    lat: xr.DataArray,
    lon: xr.DataArray,
    *,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> xr.DataArray:
    """Boolean mask for a lon/lat box (supports 1D coords and 2D curvilinear)."""
    lat_vals = np.asarray(lat, float)
    lon_180 = _lon_to_180(lon)
    if lat_vals.ndim == 1 and np.asarray(lon, float).ndim == 1:
        lat_ok = (lat_vals >= lat_min) & (lat_vals <= lat_max)
        lon_ok = (np.asarray(lon_180, float) >= lon_min) & (
            np.asarray(lon_180, float) <= lon_max
        )
        return xr.DataArray(
            np.outer(lat_ok, lon_ok),
            dims=(lat.dims[0], lon.dims[0]),
            coords={lat.dims[0]: lat, lon.dims[0]: lon},
        )
    return (lat >= lat_min) & (lat <= lat_max) & (lon_180 >= lon_min) & (lon_180 <= lon_max)


def area_weighted_regional_mean(
    da: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray,
    *,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> np.ndarray:
    """cos(lat)-weighted regional mean over a lon/lat box, per timestep."""
    time_dim = "time" if "time" in da.dims else da.dims[0]
    spatial_dims = [d for d in da.dims if d != time_dim]
    region = rect_region_mask(
        lat, lon, lon_min=lon_min, lon_max=lon_max, lat_min=lat_min, lat_max=lat_max
    )
    ocean = da.max(dim=time_dim) > 0
    region = region & ocean
    da = da.where(region)
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel({time_dim: 0}, drop=True))
    w = w.where(region)
    weighted = (da * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.notnull()).sum(dim=spatial_dims, skipna=True)
    return (weighted / norm).values


def smooth_annual_series(values: np.ndarray, *, sigma_yr: float) -> np.ndarray:
    """Gaussian smooth along an annual series (``sigma`` in years)."""
    if sigma_yr <= 0 or len(values) < 2:
        return values.astype(float)
    out = gaussian_filter1d(np.asarray(values, float), sigma=sigma_yr, mode="nearest")
    return np.where(np.isfinite(values), out, np.nan)


def spg_mlotst_timeseries(ds: xr.Dataset) -> np.ndarray:
    """SPG regional annual-max ``mlotst`` (unsmoothed)."""
    da = ds["mlotst"]
    lat, lon = lat_lon_fields(ds, da)
    return area_weighted_regional_mean(
        da,
        lat,
        lon,
        lon_min=SPG_LON_MIN,
        lon_max=SPG_LON_MAX,
        lat_min=SPG_LAT_MIN,
        lat_max=SPG_LAT_MAX,
    )


def discover_sivol(sivol_dir: Path) -> dict[str, Path]:
    """Map model id -> merged monthly ``sivol`` NetCDF."""
    out: dict[str, Path] = {}
    for path in sorted(sivol_dir.glob("sivol_*.nc")):
        if path.name.startswith("."):
            continue
        parts = path.name.split("_")
        if len(parts) < 4 or parts[0] != "sivol":
            continue
        out[parts[2]] = path
    return out


def _hemisphere_box(hemisphere: str) -> tuple[float, float, float, float]:
    if hemisphere == "arctic":
        return -180.0, 180.0, ARCTIC_LAT_MIN, ARCTIC_LAT_MAX
    if hemisphere == "antarctic":
        return -180.0, 180.0, ANTARCTIC_LAT_MIN, ANTARCTIC_LAT_MAX
    raise ValueError(f"hemisphere must be 'arctic' or 'antarctic', got {hemisphere!r}")


def sivol_ylabel(hemisphere: str, *, annual_stat: str = "mean") -> str:
    cap = "Arctic" if hemisphere == "arctic" else "Antarctic"
    lat_band = "≥60°N" if hemisphere == "arctic" else "≤50°S"
    stat = {"mean": "annual-mean", "min": "annual-minimum", "max": "annual-maximum"}.get(
        annual_stat, annual_stat
    )
    return f"{cap} ({lat_band}) regional-mean {stat} sea-ice volume per area (m)"


def polar_sivol_timeseries(
    ds: xr.Dataset,
    *,
    hemisphere: str,
    annual_stat: str = "mean",
    smooth_sigma_yr: float = GAUSSIAN_SIGMA_YR,
) -> tuple[np.ndarray, np.ndarray]:
    """Polar regional-mean ``sivol`` on an annual axis."""
    decoded = xr.decode_cf(ds, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    da = decoded["sivol"]
    lat, lon = lat_lon_fields(decoded, da)
    lon_min, lon_max, lat_min, lat_max = _hemisphere_box(hemisphere)
    time_dim = "time" if "time" in da.dims else da.dims[0]
    spatial_dims = [d for d in da.dims if d != time_dim]
    region = rect_region_mask(
        lat, lon, lon_min=lon_min, lon_max=lon_max, lat_min=lat_min, lat_max=lat_max
    )
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel({time_dim: 0}, drop=True))
    w = w.where(region)
    weighted = (da.where(region) * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.where(region).notnull()).sum(dim=spatial_dims, skipna=True)
    regional = weighted / norm
    grouped = regional.groupby("time.year")
    if annual_stat == "mean":
        annual = grouped.mean("time")
    elif annual_stat == "min":
        annual = grouped.min("time")
    else:
        annual = grouped.max("time")
    years = annual["year"].values.astype(float)
    values = smooth_annual_series(annual.values.astype(float), sigma_yr=smooth_sigma_yr)
    return years, values


def open_sivol_timeseries(
    path: Path | str,
    *,
    hemisphere: str,
    annual_stat: str = "mean",
    smooth_sigma_yr: float = GAUSSIAN_SIGMA_YR,
) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(path, decode_times=False) as ds:
        return polar_sivol_timeseries(
            ds,
            hemisphere=hemisphere,
            annual_stat=annual_stat,
            smooth_sigma_yr=smooth_sigma_yr,
        )
