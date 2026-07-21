"""
regrid_export.py
================
Remap a *categorical* TOAD cluster export onto the common global-warming-level
(GWL) grid, ready for multi-model aggregation (MMA).

This is the categorical sibling of :func:`tipmip_gwl.product.remap_to_gwl`.
``remap_to_gwl`` is for *continuous* diagnostics: it samples a variable at the
fractional years where each GWL is reached (``year_of_gwl``) and linearly
interpolates. That interpolation is wrong for cluster labels, where ``5.7`` is
not "between cluster 5 and cluster 6" and ``-1`` (noise) must not be averaged
with real events.

Instead we *forward-bin*: every export timestep is placed in the GWL bin it
falls into, and the labels landing in a bin are reduced to a single
representative label per pixel (non-noise wins; among real labels the most
frequent wins).

Two entry points:

* :func:`remap_export_to_gwl` — export is on a calendar-year (or zero-based year)
  axis; GWL at each year comes from the mapping's ``gwl_axis(year)``.
* :func:`bin_export_to_gwl` — export is already on a continuous GWL axis
  (e.g. after :func:`tipmip_gwl.product.relabel_to_gwl` in preprocessing).

Dependencies: numpy, xarray.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .mapping import GWL_GRID_STEP, gwl_grid

__all__ = [
    "bin_export_to_gwl",
    "export_on_continuous_gwl",
    "remap_export_to_gwl",
]


def _reduce_block(block: np.ndarray) -> np.ndarray:
    """Reduce a (n_years, n_pixels) block of labels to one label per pixel.

    Rule: ignore noise (``-1``) and NaN; if a pixel has any real label, return
    its most frequent one (ties broken by lowest label id); otherwise NaN.
    Vectorised for the common case (a pixel carries a single label across the
    bin); the per-pixel tie-break loop runs only on the rare multi-label pixels.
    """
    n_pix = block.shape[1]
    out = np.full(n_pix, np.nan, dtype=np.float32)

    valid = np.isfinite(block) & (block >= 0)
    any_valid = valid.any(axis=0)
    if not any_valid.any():
        return out

    # Default = first valid label down the year axis (correct whenever a pixel
    # carries a single label across the bin, which is the overwhelming case).
    first_idx = valid.argmax(axis=0)
    cols = np.arange(n_pix)
    out[any_valid] = block[first_idx, cols][any_valid]

    # Refine only pixels that actually carry more than one distinct real label.
    # Restrict to valid columns so np.nanmin/max never see an all-NaN slice.
    valid_cols = np.where(any_valid)[0]
    masked = np.where(valid[:, valid_cols], block[:, valid_cols], np.nan)
    vmin = np.nanmin(masked, axis=0)
    vmax = np.nanmax(masked, axis=0)
    multi = valid_cols[vmin != vmax]
    for p in multi:
        labels = block[valid[:, p], p].astype(np.int64)
        u, counts = np.unique(labels, return_counts=True)
        out[p] = float(u[np.argmax(counts)])  # np.unique sorts -> lowest id on tie
    return out


def export_on_continuous_gwl(export, label_var: str | None = None) -> bool:
    """True when a TOAD export's leading axis already holds GWL values (degC)."""
    da, _ = _select_label_da(export, label_var)
    time_dim = da.dims[0]
    coord = da[time_dim]
    units = str(coord.attrs.get("units", "")).lower()
    if "degc" in units:
        return True
    return coord.attrs.get("long_name") == "global warming level"


def _select_label_da(export, label_var: str | None = None) -> tuple[xr.DataArray, str]:
    if isinstance(export, xr.Dataset):
        if label_var is None:
            label_var = "cluster" if "cluster" in export.data_vars else None
        if label_var is None:
            data_vars = list(export.data_vars)
            if len(data_vars) != 1:
                raise ValueError(
                    "export is a Dataset with multiple variables; pass "
                    f"label_var=... (one of {data_vars})"
                )
            label_var = data_vars[0]
        da = export[label_var]
    else:
        da = export
        label_var = da.name or "cluster"
    return da, label_var


def _forward_bin_categorical_export(
    export,
    gwl_at_timestep: np.ndarray,
    *,
    label_var: str | None = None,
    gwl_step: float = GWL_GRID_STEP,
    gwl_max: float = 4.0,
    gwl_attrs: dict | None = None,
    remap_method: str,
    history_suffix: str = "remapped to GWL by tipmip_gwl",
):
    """Forward-bin categorical labels from per-timestep GWL onto the common grid."""
    is_dataset = isinstance(export, xr.Dataset)
    da, label_var = _select_label_da(export, label_var)
    time_dim = da.dims[0]
    spatial_dims = da.dims[1:]
    grid = gwl_grid(gwl_step, gwl_max)

    gwl_at_timestep = np.asarray(gwl_at_timestep, dtype=float)
    if gwl_at_timestep.shape != (da.sizes[time_dim],):
        raise ValueError(
            f"gwl_at_timestep must have length {da.sizes[time_dim]}, "
            f"got {gwl_at_timestep.shape}"
        )

    edges = np.concatenate(([-np.inf], (grid[:-1] + grid[1:]) / 2.0, [np.inf]))
    bin_idx = np.full(gwl_at_timestep.shape, -1, dtype=np.int64)
    valid = np.isfinite(gwl_at_timestep) & (
        gwl_at_timestep >= grid[0]
    ) & (gwl_at_timestep <= grid[-1])
    bin_idx[valid] = np.clip(
        np.digitize(gwl_at_timestep[valid], edges) - 1, 0, grid.size - 1
    )

    arr = np.asarray(da.values)
    flat = arr.reshape(arr.shape[0], -1)
    out = np.full((grid.size, flat.shape[1]), np.nan, dtype=np.float32)
    for b in range(grid.size):
        rows = np.where(bin_idx == b)[0]
        if rows.size:
            out[b] = _reduce_block(flat[rows])

    out = out.reshape((grid.size,) + arr.shape[1:])

    if gwl_attrs is None:
        gwl_attrs = {"long_name": "global warming level", "units": "degC"}

    coords = {"gwl": ("gwl", grid)}
    for d in spatial_dims:
        if d in da.coords:
            coords[d] = da[d]
    for name, c in da.coords.items():
        if name == time_dim or name in coords:
            continue
        if set(c.dims).issubset(set(spatial_dims)):
            coords[name] = c

    attrs = dict(da.attrs)
    attrs["remapped_to"] = "global warming level (gwl)"
    attrs["remap_method"] = remap_method
    result = xr.DataArray(
        out,
        dims=("gwl",) + spatial_dims,
        coords=coords,
        name=label_var,
        attrs=attrs,
    )
    result["gwl"].attrs.update(gwl_attrs)

    if is_dataset:
        ds_out = result.to_dataset(name=label_var)
        ds_out.attrs.update(export.attrs)
        ds_out.attrs["history"] = (
            ds_out.attrs.get("history", "") + f"; {history_suffix}"
        ).lstrip("; ")
        ds_out.attrs["gwl_step"] = gwl_step
        ds_out.attrs["gwl_max"] = gwl_max
        return ds_out
    return result


def bin_export_to_gwl(
    export,
    *,
    label_var: str | None = None,
    gwl_step: float = GWL_GRID_STEP,
    gwl_max: float = 4.0,
):
    """Forward-bin a categorical export already on a continuous GWL axis.

    Use when shift detection and clustering ran on a continuous GWL coordinate
    (via :func:`tipmip_gwl.product.relabel_to_gwl`) and the export's leading
    dimension already holds warming levels in degC.
    """
    da, _ = _select_label_da(export, label_var)
    time_dim = da.dims[0]
    gwl_vals = np.asarray(da[time_dim].values, dtype=float)
    return _forward_bin_categorical_export(
        export,
        gwl_vals,
        label_var=label_var,
        gwl_step=gwl_step,
        gwl_max=gwl_max,
        gwl_attrs=dict(da[time_dim].attrs),
        remap_method=(
            f"forward-binned from continuous GWL axis onto {gwl_step} degC grid "
            f"(0-{gwl_max} degC); per-pixel label reduction "
            "(non-noise wins, most frequent label, ties -> lowest id)"
        ),
        history_suffix="binned to GWL grid by tipmip_gwl",
    )


def remap_export_to_gwl(
    export,
    mapping: xr.Dataset,
    *,
    label_var: str | None = None,
    export_start_year: int | None = None,
    gwl_step: float = GWL_GRID_STEP,
    gwl_max: float = 4.0,
):
    """Remap a TOAD cluster export onto the common GWL grid by forward-binning.

    Parameters
    ----------
    export : xarray.DataArray or xarray.Dataset
        A TOAD MMA cluster export (``Conventions = TOAD_cluster_labels_v1``).
        The first dimension of the label variable is treated as the time axis;
        remaining dimensions (e.g. ``hp_pixel``, or ``j``/``i``) are spatial and
        are carried through unchanged. Labels are real cluster ids ``>= 0`` with
        ``-1`` for noise (NaN also treated as no-event).
    mapping : xarray.Dataset
        A ``gwlmap_*.nc`` product for the *same model*. Must provide
        ``gwl_axis(year)`` (the monotone forward transform). The bin grid is
        built from ``gwl_step`` and ``gwl_max`` (not taken from ``mapping['gwl']``,
        so you can bin finer or coarser than the 0.02 degC grid stored in the
        mapping product).
    label_var : str, optional
        Name of the label variable when ``export`` is a Dataset. Defaults to
        ``"cluster"`` if present, else the sole data variable.
    export_start_year : int, optional
        Calendar year of the export's first timestep. Use this when the export
        time axis is zero-based (TOAD often subtracts the start). When omitted,
        the export's time coordinate is assumed to already hold calendar years.
    gwl_step : float
        Width of each GWL bin in degC (default ``0.02``). All models in an MMA
        run should use the same step.
    gwl_max : float
        Upper end of the GWL grid in degC (default ``4.0``).

    Returns
    -------
    Same type as ``export`` (DataArray or single-variable Dataset), with the
    time dimension replaced by ``gwl``. Bins not reached by the run, or reached
    only by noise, are NaN.
    """
    da, label_var = _select_label_da(export, label_var)
    time_dim = da.dims[0]

    t_raw = np.asarray(da[time_dim].values)
    if export_start_year is not None:
        export_years = (t_raw - t_raw.min()).astype(float) + float(export_start_year)
    else:
        export_years = t_raw.astype(float)

    map_years = np.asarray(mapping["year"].values, dtype=float)
    gwl_axis = np.asarray(mapping["gwl_axis"].values, dtype=float)

    finite = np.isfinite(gwl_axis)
    if finite.sum() < 2:
        raise ValueError("mapping['gwl_axis'] has fewer than two finite values")
    yr_f = map_years[finite]
    gwl_f = gwl_axis[finite]
    y_lo, y_hi = yr_f.min(), yr_f.max()

    overlap = (export_years >= y_lo) & (export_years <= y_hi)
    if not overlap.any():
        hint = ""
        if export_start_year is None and float(t_raw.min()) < y_lo:
            hint = (
                " The export time axis looks zero-based; pass export_start_year="
                f"{int(round(y_lo))} (the mapping's rampup_start_year)."
            )
        raise ValueError(
            "no export year overlaps the mapping year range "
            f"[{int(y_lo)}, {int(y_hi)}] (export covers "
            f"[{export_years.min():.0f}, {export_years.max():.0f}]).{hint}"
        )

    gwl_of_year = np.full(export_years.shape, np.nan)
    gwl_of_year[overlap] = np.interp(export_years[overlap], yr_f, gwl_f)

    if "gwl" in mapping.coords:
        gwl_attrs = dict(mapping["gwl"].attrs)
    else:
        gwl_attrs = {"long_name": "global warming level", "units": "degC"}

    return _forward_bin_categorical_export(
        export,
        gwl_of_year,
        label_var=label_var,
        gwl_step=gwl_step,
        gwl_max=gwl_max,
        gwl_attrs=gwl_attrs,
        remap_method=(
            f"forward-binned by gwl_axis(year) onto {gwl_step} degC grid "
            f"(0-{gwl_max} degC); per-pixel label reduction "
            "(non-noise wins, most frequent label, ties -> lowest id)"
        ),
    )
