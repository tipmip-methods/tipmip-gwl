"""
io.py
=====
Reading global-mean ``tas`` NetCDF files and discovering them on disk.

The headline function is :func:`load_gmsat_nc`, which returns a calendar-aware,
**days-in-month weighted** annual GMSAT series. This is the protocol-correct
annual mean; do NOT rely on ``cdo yearmean`` (unweighted) or even ``yearmonmean``
(equal-month) for the baseline, because a differential seasonal-cycle-weighting
error between a model's piControl and its ramp-up lands directly on the zero
point you match everyone against.

Dependencies: numpy, xarray.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr


def _pick_data_var(ds: xr.Dataset) -> str:
    if "tas" in ds.data_vars:
        return "tas"
    for name, da in ds.data_vars.items():
        if name.endswith("_bnds") or name.endswith("_bounds"):
            continue
        if "time" in da.dims:
            return name
    raise ValueError(f"No time-dependent data variable found in {list(ds.data_vars)}")


def load_gmsat_nc(path):
    """Load a global-mean ``tas`` file and return (years, annual_gmsat).

    The file is expected to be already reduced to a single spatial point
    (``cdo -fldmean``, area weighted). Input may be monthly or annual:

    * monthly -> a **days-in-month weighted** annual mean is computed using the
      file's own calendar (``time.dt.days_in_month``), which is the protocol mean.
    * annual  -> passes through unchanged (the weighting is a no-op per year).

    Returns numpy arrays sorted by year.
    """
    try:  # new xarray prefers a coder instance; fall back for older versions
        ds = xr.open_dataset(
            path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True)
        )
    except (AttributeError, TypeError):
        ds = xr.open_dataset(path, use_cftime=True)
    try:
        var = _pick_data_var(ds)
        da = ds[var]
        # collapse any singleton spatial dims left by fldmean
        for dim in list(da.dims):
            if dim != "time" and da.sizes[dim] == 1:
                da = da.isel({dim: 0}, drop=True)
        da = da.squeeze(drop=True)

        weights = ds["time"].dt.days_in_month
        num = (da * weights).groupby("time.year").sum(skipna=True)
        den = weights.groupby("time.year").sum(skipna=True)
        annual = num / den

        years = annual["year"].values.astype(float)
        vals = annual.values.astype(float)
    finally:
        ds.close()

    order = np.argsort(years)
    return years[order], vals[order]


def read_attrs(path) -> dict:
    """Global attrs plus the time-coordinate calendar (lives on the coord)."""
    ds = xr.open_dataset(path, decode_times=False)
    try:
        attrs = dict(ds.attrs)
        cal = None
        if "time" in ds.variables:
            cal = ds["time"].attrs.get("calendar")
        attrs["_time_calendar"] = cal
    finally:
        ds.close()
    return attrs


def _model_from_name(path: Path) -> str:
    # tas_<table>_<model>_<exp>_<member>_<grid>_<suffix>.nc
    return path.name.split("_")[2]


def discover(dir_path) -> dict:
    """Map model -> file for every *.nc in a directory."""
    out = {}
    for p in sorted(Path(dir_path).glob("*.nc")):
        out[_model_from_name(p)] = p
    return out
