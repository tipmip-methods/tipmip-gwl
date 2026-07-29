"""Shared helpers for paper diagnostic-remap figures (native annual-max mlotst)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl.io import model_label

# Subpolar Gyre box used in paper mlotst figures (lon/lat in degrees).
SPG_LON_MIN = -70.0
SPG_LON_MAX = -10.0
SPG_LAT_MIN = 45.0
SPG_LAT_MAX = 60.0
SPG_MLOTST_YLABEL = "SPG regional-mean annual-max mixed-layer depth (m)"
GLOBAL_MLOTST_YLABEL = "Global-mean annual-max mixed-layer depth (m)"
SPG_GAUSSIAN_SIGMA_YR = 6.0


def lat_name(ds: xr.Dataset) -> str:
    for name in ("latitude", "lat"):
        if name in ds.coords:
            return name
    raise KeyError(f"no latitude coordinate found among {list(ds.coords)}")


def lon_name(ds: xr.Dataset) -> str:
    for name in ("longitude", "lon"):
        if name in ds.coords:
            return name
    raise KeyError(f"no longitude coordinate found among {list(ds.coords)}")


def lon_to_180(lon: xr.DataArray | np.ndarray) -> np.ndarray:
    """Wrap longitudes to [-180, 180] degrees."""
    return ((np.asarray(lon, dtype=np.float64) + 180.0) % 360.0) - 180.0


def lat_lon_fields(ds: xr.Dataset, da: xr.DataArray) -> tuple[xr.DataArray, xr.DataArray]:
    """Return 2D latitude/longitude fields aligned with ``da``'s spatial grid.

    Regular lat/lon grids (1D coordinates) are broadcast to the diagnostic's
    spatial shape; curvilinear 2D coordinates are returned unchanged.
    """
    lat = ds[lat_name(ds)]
    lon = ds[lon_name(ds)]
    time_dim = _time_dim(da)
    template = da.isel({time_dim: 0}, drop=True)
    if lat.ndim == 1 and lon.ndim == 1:
        return lat.broadcast_like(template), lon.broadcast_like(template)
    if lat.ndim == 2 and lon.ndim == 2 and lat.dims == lon.dims:
        return lat, lon
    raise ValueError(
        f"unsupported lat/lon layout: lat dims={lat.dims}, lon dims={lon.dims}"
    )


def rect_region_mask(
    lat: xr.DataArray | np.ndarray,
    lon: xr.DataArray | np.ndarray,
    *,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> xr.DataArray:
    """Boolean mask for a lat/lon box on 2D coordinate fields.

    Longitudes are normalised to [-180, 180] before comparison so the mask is
    correct whether the native grid stores 0-360 or -180-180. ``lat`` and ``lon``
    must already share the same shape/dims (see :func:`lat_lon_fields`).
    """
    lat_arr = lat if isinstance(lat, xr.DataArray) else xr.DataArray(lat)
    lon_arr = (
        lon
        if isinstance(lon, xr.DataArray)
        else xr.DataArray(lon, dims=lat_arr.dims, coords=lat_arr.coords)
    )
    lon180 = lon_to_180(lon_arr)
    return (
        (lon180 >= lon_min)
        & (lon180 <= lon_max)
        & (lat_arr >= lat_min)
        & (lat_arr <= lat_max)
    )


def _time_dim(da: xr.DataArray) -> str:
    for name in ("time", "gwl", "year"):
        if name in da.dims:
            return name
    raise KeyError(f"no time-like dimension found among {da.dims}")


def area_weighted_mean(
    da: xr.DataArray,
    lat: xr.DataArray,
    *,
    region_mask: xr.DataArray | None = None,
) -> np.ndarray:
    """cos(latitude)-weighted mean over spatial dims, optionally within a region.

    Grid cells whose temporal maximum ``mlotst`` is zero are excluded (UKESM
    encodes land as 0 rather than NaN on the native ORCA tripolar grid).
    """
    time_dim = _time_dim(da)
    spatial_dims = [d for d in da.dims if d != time_dim]
    ocean = da.max(dim=time_dim) > 0
    keep = ocean if region_mask is None else ocean & region_mask
    da = da.where(keep)
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel({time_dim: 0}, drop=True))
    w = w.where(keep)
    weighted = (da * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.notnull()).sum(dim=spatial_dims, skipna=True)
    return (weighted / norm).values


def area_weighted_global_mean(da: xr.DataArray, lat: xr.DataArray) -> np.ndarray:
    """cos(latitude)-weighted global mean over the spatial dims, per timestep."""
    return area_weighted_mean(da, lat)


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
    """cos(latitude)-weighted regional mean for a lon/lat box."""
    region = rect_region_mask(
        lat, lon, lon_min=lon_min, lon_max=lon_max, lat_min=lat_min, lat_max=lat_max
    )
    return area_weighted_mean(da, lat, region_mask=region)


def spg_mlotst_timeseries(
    ds: xr.Dataset,
    *,
    lon_min: float = SPG_LON_MIN,
    lon_max: float = SPG_LON_MAX,
    lat_min: float = SPG_LAT_MIN,
    lat_max: float = SPG_LAT_MAX,
) -> np.ndarray:
    """SPG regional mean of ``mlotst`` (annual-max, cos-lat weighted)."""
    da = ds["mlotst"]
    lat, lon = lat_lon_fields(ds, da)
    return area_weighted_regional_mean(
        da,
        lat,
        lon,
        lon_min=lon_min,
        lon_max=lon_max,
        lat_min=lat_min,
        lat_max=lat_max,
    )


def smooth_annual_series(
    values: np.ndarray,
    *,
    sigma_yr: float = SPG_GAUSSIAN_SIGMA_YR,
) -> np.ndarray:
    """Gaussian smooth along an annual time axis (``sigma_yr`` in years).

    Applied to the calendar-time series *before* ``relabel_to_gwl`` /
    ``resample_to_gwl``, matching ``fig_spg.py`` (6 yr) and
    ``plot_hysteresis_compare.py``.
    """
    from scipy.ndimage import gaussian_filter1d

    vals = np.asarray(values, dtype=float)
    if sigma_yr <= 0 or vals.size == 0:
        return vals
    return gaussian_filter1d(vals, sigma=sigma_yr)


def mapping_index_by_leg(mapping_dir: Path, leg: str) -> dict[str, Path]:
    """Index ``gwlmap_*.nc`` products by model id for a logical ``leg`` alias."""
    from tipmip_gwl.product import (
        _experiment_matches_leg,
        _normalize_leg,
        _parse_mapping_filename,
    )

    leg = _normalize_leg(leg)
    out: dict[str, Path] = {}
    for path in sorted(mapping_dir.glob("gwlmap_*.nc")):
        parsed = _parse_mapping_filename(path)
        if parsed is None:
            continue
        _model, exp, _ver = parsed
        if not _experiment_matches_leg(exp, leg):
            continue
        with xr.open_dataset(path) as ds:
            mid = model_label(dict(ds.attrs))
        out[mid] = path
    return out


def mapping_index_by_rampup_model(mapping_dir: Path) -> dict[str, Path]:
    """Index gwlmap_*.nc ramp-up products by canonical model id."""
    return mapping_index_by_leg(mapping_dir, "ramp-up")


def calendar_years(ds: xr.Dataset) -> np.ndarray:
    """Decode a CF ``time`` coordinate to integer calendar years."""
    try:
        decoded = xr.decode_cf(
            ds, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True)
        )
    except (AttributeError, TypeError):
        decoded = xr.decode_cf(ds)
    years = []
    for t in decoded["time"].values:
        if hasattr(t, "year"):
            years.append(int(t.year))
        else:
            years.append(int(np.datetime64(t, "Y")))
    return np.asarray(years, dtype=float)


def discover_native_mlotst(mlotst_dir: Path) -> dict[str, Path]:
    """Map model -> native-time mlotst file, skipping pre-remapped GWL-axis products.

    The staging dir may also hold ``*_annualmax_toad.nc`` files (already on a
    GWL axis from an external pipeline) and transient ``.toad-save-*.nc`` scratch
    files; paper demos need the original ``*_annualmax.nc`` calendar-time series.
    """
    out: dict[str, Path] = {}
    for p in sorted(mlotst_dir.glob("mlotst_*.nc")):
        if p.name.startswith(".") or "_toad" in p.name:
            continue
        parts = p.name.split("_")
        if len(parts) < 5:
            continue
        out[parts[2]] = p
    return out
