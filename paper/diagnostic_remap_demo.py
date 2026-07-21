"""
Two-panel proof-of-concept: remap a diagnostic variable (mixed-layer depth)
from calendar time onto the common GWL axis, using each model's published
mapping product.

Panel (a) plots each model's global-mean annual-max mlotst against native
years-since-ramp-up-start. Panel (b) relabels the same series with each year's
GWL via ``relabel_to_gwl`` (native forward map, not ``resample_to_gwl``).

Usage::

    python paper/diagnostic_remap_demo.py --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 --mapping-dir mapping
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PAPER = Path(__file__).resolve().parent
if str(_PAPER) not in sys.path:
    sys.path.insert(0, str(_PAPER))

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.patches import FancyArrowPatch

from tipmip_gwl.product import relabel_to_gwl

from mlotst_remap_helpers import (
    area_weighted_global_mean,
    calendar_years,
    discover_native_mlotst,
    lat_name,
    mapping_index_by_rampup_model,
)

GWL_MAX = 4.0


def main(mlotst_dir, mapping_dir, out_path):
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)

    mlotst_files = discover_native_mlotst(mlotst_dir)
    mapping_files = mapping_index_by_rampup_model(mapping_dir)
    models = sorted(set(mlotst_files) & set(mapping_files))
    missing = sorted(set(mlotst_files) ^ set(mapping_files))
    if missing:
        print(f"note: skipping models present on only one side: {missing}")

    colors = {m: plt.cm.Dark2.colors[i % 8] for i, m in enumerate(models)}

    series = {}
    for model in models:
        with xr.open_dataset(mlotst_files[model], decode_times=False) as ds:
            years_cal = calendar_years(ds)
            gmean = area_weighted_global_mean(ds["mlotst"], ds[lat_name(ds)])

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
    fig.add_artist(
        FancyArrowPatch(
            (x0, mid_y),
            (x1, mid_y),
            transform=fig.transFigure,
            arrowstyle="-|>",
            mutation_scale=14,
            lw=1.8,
            color="0.4",
            zorder=5,
        )
    )
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
