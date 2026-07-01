"""
regrid_export.py
================
Remap a *categorical* TOAD cluster export from a calendar-year axis onto the
common global-warming-level (GWL) grid, ready for multi-model aggregation (MMA).

This is the categorical sibling of :func:`tipmip_gwl.product.remap_to_gwl`.
``remap_to_gwl`` is for *continuous* diagnostics: it samples a variable at the
fractional years where each GWL is reached (``year_of_gwl``) and linearly
interpolates. That interpolation is wrong for cluster labels, where ``5.7`` is
not "between cluster 5 and cluster 6" and ``-1`` (noise) must not be averaged
with real events.

Instead we *forward-bin*: every export year is placed in the GWL bin it falls
into via the forward transform ``gwl_axis(year)``, and the labels landing in a
bin are reduced to a single representative label per pixel (non-noise wins; among
real labels the most frequent wins). Shift detection and clustering therefore
stay on each model's native annual axis (full temporal resolution); only the
*labels* are moved onto the shared axis, just before aggregation::

    shift detection -> clustering -> remap_export_to_gwl -> MMA

Alignment is by calendar-year *value*, using the mapping's ``year`` coordinate as
the authority. TOAD exports often zero-base their time axis; pass
``export_start_year`` so it can be restored to calendar years.

Dependencies: numpy, xarray.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .mapping import gwl_grid

__all__ = ["remap_export_to_gwl"]


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


def remap_export_to_gwl(
    export,
    mapping: xr.Dataset,
    *,
    label_var: str | None = None,
    export_start_year: int | None = None,
    gwl_step: float = 0.1,
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
        A ``gwlmap_*.nc`` product for the *same model``. Must provide
        ``gwl_axis(year)`` (the monotone forward transform). The bin grid is
        built from ``gwl_step`` and ``gwl_max`` (not taken from ``mapping['gwl']``,
        so you can bin finer or coarser than the 0.1 degC grid stored in the
        mapping product).
    label_var : str, optional
        Name of the label variable when ``export`` is a Dataset. Defaults to
        ``"cluster"`` if present, else the sole data variable.
    export_start_year : int, optional
        Calendar year of the export's first timestep. Use this when the export
        time axis is zero-based (TOAD often subtracts the start). When omitted,
        the export's time coordinate is assumed to already hold calendar years.
    gwl_step : float
        Width of each GWL bin in degC (default ``0.1``). Use e.g. ``0.05`` for
        finer bins. All models in an MMA run should use the same step.
    gwl_max : float
        Upper end of the GWL grid in degC (default ``4.0``).

    Returns
    -------
    Same type as ``export`` (DataArray or single-variable Dataset), with the
    time dimension replaced by ``gwl``. Bins not reached by the run, or reached
    only by noise, are NaN.
    """
    is_dataset = isinstance(export, xr.Dataset)
    if is_dataset:
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

    time_dim = da.dims[0]
    spatial_dims = da.dims[1:]

    # --- calendar years of the export, aligned to the mapping's authority ----
    t_raw = np.asarray(da[time_dim].values)
    if export_start_year is not None:
        export_years = (t_raw - t_raw.min()).astype(float) + float(export_start_year)
    else:
        export_years = t_raw.astype(float)

    map_years = np.asarray(mapping["year"].values, dtype=float)
    gwl_axis = np.asarray(mapping["gwl_axis"].values, dtype=float)
    grid = gwl_grid(gwl_step, gwl_max)

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

    # Forward transform: GWL at each export year (NaN outside the mapped range).
    gwl_of_year = np.full(export_years.shape, np.nan)
    gwl_of_year[overlap] = np.interp(export_years[overlap], yr_f, gwl_f)

    # --- bin onto the common grid (edges at grid midpoints) ------------------
    edges = np.concatenate(([-np.inf], (grid[:-1] + grid[1:]) / 2.0, [np.inf]))
    bin_idx = np.full(export_years.shape, -1, dtype=np.int64)
    valid_year = np.isfinite(gwl_of_year)
    bin_idx[valid_year] = np.clip(
        np.digitize(gwl_of_year[valid_year], edges) - 1, 0, grid.size - 1
    )

    # --- reduce labels per bin ----------------------------------------------
    arr = np.asarray(da.values)
    flat = arr.reshape(arr.shape[0], -1)  # (time, n_pixels)
    out = np.full((grid.size, flat.shape[1]), np.nan, dtype=np.float32)
    for b in range(grid.size):
        rows = np.where(bin_idx == b)[0]
        if rows.size:
            out[b] = _reduce_block(flat[rows])

    out = out.reshape((grid.size,) + arr.shape[1:])

    # --- rebuild an xarray object on the gwl axis ----------------------------
    coords = {"gwl": ("gwl", grid)}
    if "gwl" in mapping.coords:
        gwl_attrs = dict(mapping["gwl"].attrs)
    else:
        gwl_attrs = {"long_name": "global warming level", "units": "degC"}
    for d in spatial_dims:
        if d in da.coords:
            coords[d] = da[d]
    # carry non-dimension spatial coords (e.g. latitude/longitude on j,i)
    for name, c in da.coords.items():
        if name == time_dim or name in coords:
            continue
        if set(c.dims).issubset(set(spatial_dims)):
            coords[name] = c

    attrs = dict(da.attrs)
    attrs["remapped_to"] = "global warming level (gwl)"
    attrs["remap_method"] = (
        f"forward-binned by gwl_axis(year) onto {gwl_step} degC grid "
        f"(0-{gwl_max} degC); per-pixel label reduction "
        "(non-noise wins, most frequent label, ties -> lowest id)"
    )
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
            ds_out.attrs.get("history", "") + "; remapped to GWL by tipmip_gwl"
        ).lstrip("; ")
        ds_out.attrs["gwl_step"] = gwl_step
        ds_out.attrs["gwl_max"] = gwl_max
        return ds_out
    return result
