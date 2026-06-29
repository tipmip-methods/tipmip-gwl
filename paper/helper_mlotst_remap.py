"""Shared helpers for paper diagnostic-remap figures (native annual-max mlotst)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl.ensemble import (
    INCLUDED_MODELS,
    MissingEnsembleDataError,
)
from tipmip_gwl.io import model_label

GLOBAL_MLOTST_YLABEL = "Global-mean annual-max mixed-layer depth (m)"


def bundled_models(*model_dicts: dict[str, object]) -> list[str]:
    """Included ensemble models present in every supplied index.

    Raises :class:`~tipmip_gwl.ensemble.MissingEnsembleDataError` if any
    :data:`~tipmip_gwl.ensemble.INCLUDED_MODELS` member is missing from the
    intersection.
    """
    allowed = set(INCLUDED_MODELS)
    if not model_dicts:
        return list(INCLUDED_MODELS)
    keys = set.intersection(*(set(d.keys()) for d in model_dicts))
    selected = sorted(keys & allowed)
    missing = [m for m in INCLUDED_MODELS if m not in selected]
    if missing:
        labels = ", ".join(f"{i}" for i, d in enumerate(model_dicts))
        raise MissingEnsembleDataError(
            "Included model(s) missing from mapping index intersection "
            f"({labels}): {', '.join(missing)}"
        )
    return selected


def lat_name(ds: xr.Dataset) -> str:
    """Name of the latitude field to area-weight ``mlotst`` by.

    CESM2's staged file only attaches ``TLONG``/``ULAT`` (U-grid) as
    coordinates; the ocean tracer grid latitude matching ``mlotst`` and
    ``TLONG`` is ``TLAT``, present as a plain data variable rather than a
    coordinate. Checking ``ds.variables`` (not just ``ds.coords``) picks it up
    without disturbing models that do have a proper ``latitude``/``lat``
    coordinate.
    """
    for name in ("latitude", "lat", "TLAT"):
        if name in ds.variables:
            return name
    raise KeyError(f"no latitude coordinate found among {list(ds.coords)}")


def _time_dim(da: xr.DataArray) -> str:
    for name in ("time", "gwl", "year"):
        if name in da.dims:
            return name
    raise KeyError(f"no time-like dimension found among {da.dims}")


def area_weighted_mean(da: xr.DataArray, lat: xr.DataArray) -> np.ndarray:
    """cos(latitude)-weighted global mean over the spatial dims, per timestep.

    Grid cells whose temporal maximum ``mlotst`` is zero are excluded (UKESM
    encodes land as 0 rather than NaN on the native ORCA tripolar grid).
    """
    time_dim = _time_dim(da)
    spatial_dims = [d for d in da.dims if d != time_dim]
    ocean = da.max(dim=time_dim) > 0
    da = da.where(ocean)
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel({time_dim: 0}, drop=True))
    w = w.where(ocean)
    weighted = (da * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.notnull()).sum(dim=spatial_dims, skipna=True)
    return (weighted / norm).values


def area_weighted_global_mean(da: xr.DataArray, lat: xr.DataArray) -> np.ndarray:
    """cos(latitude)-weighted global mean over the spatial dims, per timestep."""
    return area_weighted_mean(da, lat)


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
    """Map model -> native calendar-time ``*_annualmax.nc`` mlotst file.

    Skips pre-remapped GWL-axis products and hidden scratch files in the staging dir.
    """
    out: dict[str, Path] = {}
    for p in sorted(mlotst_dir.glob("mlotst_*.nc")):
        if p.name.startswith(".") or not p.name.endswith("_annualmax.nc"):
            continue
        parts = p.name.split("_")
        if len(parts) < 5:
            continue
        out[parts[2]] = p
    return out
