"""Shared helpers for paper diagnostic-remap figures (native annual-max mlotst)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl.io import model_label


def lat_name(ds: xr.Dataset) -> str:
    for name in ("latitude", "lat"):
        if name in ds.coords:
            return name
    raise KeyError(f"no latitude coordinate found among {list(ds.coords)}")


def area_weighted_global_mean(da: xr.DataArray, lat: xr.DataArray) -> np.ndarray:
    """cos(latitude)-weighted global mean over the spatial dims, per timestep."""
    spatial_dims = [d for d in da.dims if d != "time"]
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel(time=0, drop=True))
    weighted = (da * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.notnull()).sum(dim=spatial_dims, skipna=True)
    return (weighted / norm).values


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
