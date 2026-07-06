"""
Two-panel proof-of-concept: remap a diagnostic variable (mixed-layer depth)
from calendar time onto the common GWL axis, using each model's published
mapping product.

Data caveats (see paper caption):
* mlotst here is the annual **maximum** global-mean mixed-layer depth, not the
  annual mean used for tas (Step 1). Only annual-max mlotst is available on
  disk (already reduced by the sibling TOAD pipeline); a true annual-mean
  would require reprocessing raw monthly archives. Annual-max is arguably the
  more scientifically relevant statistic for mixed-layer depth (deep
  convection events) in any case.
* The global mean is area-weighted by cos(latitude), not the true ocean cell
  area (areacello), which is not available for these curvilinear grids. This
  is an approximation; it is not equivalent to the cdo fldmean treatment used
  for tas.
* The diagnostic itself is unsmoothed -- the 31-yr running mean is axis-only
  (Step 4) and is never applied to variables being remapped through the axis.

Panel (a) plots each model's global-mean annual-max mlotst against native
years-since-ramp-up-start. Panel (b) relabels the same (unsmoothed, native
resolution) series with each year's GWL via the model's own gwl_axis(year) --
the forward transform in its gwlmap_*.nc product (relabel_to_gwl, not
remap_to_gwl: no interpolation onto a shared grid, so nothing is smoothed or
resampled beyond the axis relabelling itself). Lines end at different GWLs
because each model's ramp-up reaches a different maximum warming level
(Step 6: NaN/dropped beyond a model's realised range, never extrapolated).

Usage::

    python paper/diagnostic_remap_demo.py --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 --mapping-dir mapping
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tipmip_gwl.io import discover
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
    """Index gwlmap_*.nc products by the model token in their rampup_file attr.

    Not by source_id: a mapping file's own source_id can differ from the model
    token embedded in filenames elsewhere (e.g. UKESM1-2-LL's staged file has
    source_id 'eUKESM1-1-ice-N96ORCA1'). rampup_file preserves the same
    ``<var>_<table>_<model>_<exp>_...`` token used by tipmip_gwl.io.discover,
    so this is what lines mlotst files up with the right mapping product.
    """
    out: dict[str, Path] = {}
    for path in sorted(mapping_dir.glob("gwlmap_*.nc")):
        with xr.open_dataset(path) as ds:
            rampup_file = ds.attrs.get("rampup_file")
        if not rampup_file:
            continue
        model = Path(rampup_file).name.split("_")[2]
        out[model] = path
    return out


def main(mlotst_dir, mapping_dir, out_path):
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)

    mlotst_files = discover(mlotst_dir)
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
            years = ds["time"].values.astype(float)  # already zero-based
            gmean = _area_weighted_global_mean(ds["mlotst"], ds[_lat_name(ds)])

        mapping_ds = xr.open_dataset(mapping_files[model])
        try:
            da = xr.DataArray(gmean, dims=("time",), coords={"time": years})
            gwl_da = relabel_to_gwl(
                mapping_ds,
                da,
                year_dim="time",
                year_offset=int(mapping_ds.attrs["rampup_start_year"]),
                new_dim="gwl",
            )
        finally:
            mapping_ds.close()

        series[model] = {
            "years": years,
            "native": gmean,
            "gwl": gwl_da["gwl"].values,
            "gwl_vals": gwl_da.values,
        }

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 6), sharey=True)

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
