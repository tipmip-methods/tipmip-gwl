"""
Two-panel proof-of-concept: remap a diagnostic variable (mixed-layer depth)
from calendar time onto the common GWL axis, using each model's published
mapping product.

Data caveats (see paper caption):
* mlotst here is the annual **maximum** global-mean mixed-layer depth, not the
  annual mean used for tas (paper Step 1). Only annual-max mlotst is available on
  disk (already reduced by the sibling TOAD pipeline); a true annual-mean
  would require reprocessing raw monthly archives. Annual-max is arguably the
  more scientifically relevant statistic for mixed-layer depth (deep
  convection events) in any case.
* The global mean is area-weighted by cos(latitude), not the true ocean cell
  area (areacello), which is not available for these curvilinear grids. This
  is an approximation; it is not equivalent to the cdo fldmean treatment used
  for tas.
* The diagnostic itself is unsmoothed -- the 31-yr running mean is axis-only
  (paper Step 2) and is never applied to variables being remapped through the axis.

Panel (a) plots each model's global-mean annual-max mlotst against native
years-since-ramp-up-start. Panel (b) relabels the same (unsmoothed, native
resolution) series with each year's GWL via the model's own gwl_axis(year) --
the forward transform in its gwlmap_*.nc product (relabel_to_gwl, not
remap_to_gwl: no interpolation onto a shared grid, so nothing is smoothed or
resampled beyond the axis relabelling itself). Lines end at different GWLs
because each model's ramp-up reaches a different maximum warming level
(paper Step 3: NaN/dropped beyond a model's realised range, never extrapolated).

Usage::

    python paper/diagnostic_remap_demo.py --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 --mapping-dir mapping
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.patches import FancyArrowPatch

from tipmip_gwl.io import model_label
from tipmip_gwl.product import relabel_to_gwl

GWL_MAX = 4.0


def _lat_name(ds: xr.Dataset) -> str:
    for name in ("latitude", "lat"):
        if name in ds.coords:
            return name
    raise KeyError(f"no latitude coordinate found among {list(ds.coords)}")


def _area_weighted_global_mean(da: xr.DataArray, lat: xr.DataArray) -> np.ndarray:
    """cos(latitude)-weighted global mean over the spatial dims, per timestep.

    Works for both 1D (regular lat/lon) and 2D (curvilinear, e.g. ocean j/i)
    latitude fields via xarray broadcasting. Approximation only: no areacello
    is available for these grids (see module docstring). NaN (land) cells are
    excluded from both the numerator and the weight normalisation.
    """
    spatial_dims = [d for d in da.dims if d != "time"]
    w = np.cos(np.deg2rad(lat)).broadcast_like(da.isel(time=0, drop=True))
    weighted = (da * w).sum(dim=spatial_dims, skipna=True)
    norm = w.where(da.notnull()).sum(dim=spatial_dims, skipna=True)
    return (weighted / norm).values


def _mapping_index_by_rampup_model(mapping_dir: Path) -> dict[str, Path]:
    """Index gwlmap_*.nc products by canonical model id."""
    out: dict[str, Path] = {}
    for path in sorted(mapping_dir.glob("gwlmap_*.nc")):
        with xr.open_dataset(path) as ds:
            if str(ds.attrs.get("leg", "ramp-up")) != "ramp-up":
                continue
            model = model_label(dict(ds.attrs))
        out[model] = path
    return out


def _calendar_years(ds: xr.Dataset) -> np.ndarray:
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


def _discover_native_mlotst(mlotst_dir: Path) -> dict[str, Path]:
    """Map model -> native-time mlotst file, skipping TOAD remapped products.

    The mlotst staging dir may also hold ``*_annualmax_toad.nc`` files (already
    on a GWL axis) and transient ``.toad-save-*.nc`` scratch files; this demo
    needs the original ``*_annualmax.nc`` series with a calendar ``time`` dim.
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


def main(mlotst_dir, mapping_dir, out_path):
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)

    mlotst_files = _discover_native_mlotst(mlotst_dir)
    mapping_files = _mapping_index_by_rampup_model(mapping_dir)
    models = sorted(set(mlotst_files) & set(mapping_files))
    missing = sorted(set(mlotst_files) ^ set(mapping_files))
    if missing:
        print(f"note: skipping models present on only one side: {missing}")

    # Dark2 color cycle in sorted-model-name order -- must match Figure 1
    # (plotting.plot_diagnostics sets the same prop_cycle and iterates diags
    # in sorted(ru_files) order).
    colors = {m: plt.cm.Dark2.colors[i % 8] for i, m in enumerate(models)}

    series = {}
    for model in models:
        with xr.open_dataset(mlotst_files[model], decode_times=False) as ds:
            years_cal = _calendar_years(ds)
            gmean = _area_weighted_global_mean(ds["mlotst"], ds[_lat_name(ds)])

        mapping_ds = xr.open_dataset(mapping_files[model])
        try:
            rampup_start = int(mapping_ds.attrs["rampup_start_year"])
            da = xr.DataArray(gmean, dims=("time",), coords={"time": years_cal})
            gwl_da = relabel_to_gwl(
                mapping_ds,
                da,
                year_dim="time",
                year_offset=0.0,
                new_dim="gwl",
            )
        finally:
            mapping_ds.close()

        series[model] = {
            "years": years_cal - rampup_start,
            "native": gmean,
            "gwl": gwl_da["gwl"].values,
            "gwl_vals": gwl_da.values,
        }

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    for model in models:
        s = series[model]
        c = colors[model]
        axA.plot(s["years"], s["native"], color=c, lw=1.5, label=model)
        axB.plot(s["gwl"], s["gwl_vals"], color=c, lw=1.5)

    # axA.set_title("Native calendar axis")
    # axB.set_title("Common GWL axis")
    axA.set_xlabel("Years since ramp-up start")
    axB.set_xlabel("GWL (°C)")
    axA.set_ylabel("Global-mean annual-max mixed-layer depth (m)")
    axB.set_xlim(0.0, GWL_MAX)
    axA.legend(ncol=2, framealpha=0.0, loc="upper right")

    fig.tight_layout()
    fig.subplots_adjust(wspace=0.32)
    pos_a, pos_b = axA.get_position(), axB.get_position()
    mid_y = (pos_a.y0 + pos_a.y1) / 2
    x0, x1 = pos_a.x1 + 0.012, pos_b.x0 - 0.012
    arrow = FancyArrowPatch(
        (x0, mid_y),
        (x1, mid_y),
        transform=fig.transFigure,
        arrowstyle="-|>",
        mutation_scale=14,
        lw=1.8,
        color="0.4",
        zorder=5,
    )
    fig.add_artist(arrow)
    fig.text(
        (x0 + x1) / 2,
        mid_y + 0.028,
        "Remapping",
        ha="center",
        va="bottom",
        fontsize=10,
        color="0.35",
        zorder=5,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved {out_path}")


DEFAULT_OUT = Path(__file__).resolve().parent / "figures" / "diagnostic_remap_demo.png"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Two-panel demo: mlotst on native time axis vs common GWL axis."
    )
    parser.add_argument("--mlotst-dir", required=True)
    parser.add_argument("--mapping-dir", default="mapping")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    main(args.mlotst_dir, args.mapping_dir, args.out)
