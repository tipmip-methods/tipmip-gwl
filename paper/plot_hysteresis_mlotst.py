"""Mixed-layer depth hysteresis: ramp-up vs ramp-down on the GWL axis.

Resamples global-mean annual-max ``mlotst`` with ``resample_to_gwl`` onto the
shared 0.02 °C grid (0–4 °C). By default uses ramp-down-from-4 °C and plots
MIROC-ES2L only, with a bottom bar panel for down minus up at each grid tick.

Usage::

    python paper/plot_hysteresis_mlotst.py \\
        --mlotst-up-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \\
        --mlotst-dn-dir ~/Desktop/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0 \\
        --mapping-dir mapping
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
from matplotlib import gridspec
from mlotst_remap_helpers import (
    area_weighted_global_mean,
    calendar_years,
    discover_native_mlotst,
    lat_name,
    mapping_index_by_leg,
)
from paper_style import model_color_map

from tipmip_gwl.mapping import GWL_GRID_STEP
from tipmip_gwl.product import resample_to_gwl

PAPER_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = PAPER_DIR / "figures" / "hysteresis_mlotst_4c.png"
DEFAULT_MODEL = "MIROC-ES2L"
DEFAULT_DN_LEG = "ramp-down-4c"
GWL_MIN = 0.0
GWL_MAX = 4.0

DN_LEG_LABELS = {
    "ramp-down-2c": "Ramp-down from 2 °C",
    "ramp-down-4c": "Ramp-down from 4 °C",
}


def _load_resampled_series(
    mlotst_path: Path,
    mapping_path: Path,
    *,
    gwl_min: float = GWL_MIN,
    gwl_max: float = GWL_MAX,
    gwl_step: float = GWL_GRID_STEP,
) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(mlotst_path, decode_times=False) as ds:
        years_cal = calendar_years(ds)
        gmean = area_weighted_global_mean(ds["mlotst"], ds[lat_name(ds)])
    with xr.open_dataset(mapping_path) as mapping_ds:
        da = xr.DataArray(gmean, dims=("time",), coords={"time": years_cal})
        resampled = resample_to_gwl(
            mapping_ds,
            da,
            year_dim="time",
            gwl_min=gwl_min,
            gwl_max=gwl_max,
            gwl_step=gwl_step,
        )
    gwl = resampled["gwl"].values.astype(float)
    return gwl, resampled.values.astype(float)


def main(
    mlotst_up_dir,
    mlotst_dn_dir,
    mapping_dir,
    out_path=DEFAULT_OUT,
    *,
    model: str = DEFAULT_MODEL,
    dn_leg: str = DEFAULT_DN_LEG,
) -> Path:
    mlotst_up_dir = Path(mlotst_up_dir)
    mlotst_dn_dir = Path(mlotst_dn_dir)
    mapping_dir = Path(mapping_dir)

    if dn_leg not in DN_LEG_LABELS:
        raise SystemExit(
            f"Unknown dn_leg {dn_leg!r}; choose from {sorted(DN_LEG_LABELS)}"
        )

    gwl_max = GWL_MAX if dn_leg == "ramp-down-4c" else 3.0

    up_mlotst = discover_native_mlotst(mlotst_up_dir)
    dn_mlotst = discover_native_mlotst(mlotst_dn_dir)
    up_maps = mapping_index_by_leg(mapping_dir, "ramp-up")
    dn_maps = mapping_index_by_leg(mapping_dir, dn_leg)

    if model not in up_mlotst or model not in dn_mlotst:
        raise SystemExit(f"Model {model!r} not found in both mlotst directories")
    if model not in up_maps or model not in dn_maps:
        raise SystemExit(f"No ramp-up / {dn_leg!r} mapping for {model!r}")

    gwl, vals_up = _load_resampled_series(
        up_mlotst[model], up_maps[model], gwl_max=gwl_max
    )
    _, vals_dn = _load_resampled_series(
        dn_mlotst[model], dn_maps[model], gwl_max=gwl_max
    )

    both = np.isfinite(vals_up) & np.isfinite(vals_dn)
    delta = np.full_like(vals_up, np.nan)
    delta[both] = vals_dn[both] - vals_up[both]

    color = model_color_map([model])[model]

    fig = plt.figure(figsize=(6.8, 5.2))
    gs = gridspec.GridSpec(
        2,
        1,
        figure=fig,
        height_ratios=[3.2, 1.0],
        hspace=0.06,
    )
    ax_main = fig.add_subplot(gs[0])
    ax_delta = fig.add_subplot(gs[1], sharex=ax_main)

    up_mask = np.isfinite(vals_up)
    dn_mask = np.isfinite(vals_dn)
    ax_main.plot(gwl[up_mask], vals_up[up_mask], color=color, lw=2.2, label="Ramp-up")
    ax_main.plot(
        gwl[dn_mask],
        vals_dn[dn_mask],
        color=color,
        lw=1.0,
        label=DN_LEG_LABELS[dn_leg],
    )
    ax_main.set_xlim(GWL_MIN, gwl_max)
    ax_main.set_ylabel("Global-mean annual-max mixed-layer depth (m)")
    ax_main.set_title(f"{model}: mixed-layer depth on the common GWL grid", fontsize=11)
    ax_main.legend(framealpha=0.9, loc="upper right")
    ax_main.tick_params(labelbottom=False)

    bar_gwl = gwl[both]
    bar_delta = delta[both]
    ax_delta.bar(
        bar_gwl,
        bar_delta,
        width=GWL_GRID_STEP * 0.92,
        color=color,
        alpha=0.55,
        align="center",
        edgecolor="none",
    )
    ax_delta.axhline(0.0, color="0.35", lw=0.6)
    ax_delta.set_xlim(GWL_MIN, gwl_max)
    ax_delta.set_xlabel("GWL (°C)")
    ax_delta.set_ylabel(r"$\Delta$ depth (down $-$ up, m)")
    ax_delta.yaxis.set_label_position("right")
    ax_delta.yaxis.tick_right()
    ax_delta.tick_params(axis="y", which="both", left=False, labelleft=False)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path} ({model}; {dn_leg}; resample_to_gwl)")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mlotst-up-dir", required=True)
    parser.add_argument("--mlotst-dn-dir", required=True)
    parser.add_argument("--mapping-dir", default="mapping")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="single model to plot")
    parser.add_argument(
        "--dn-leg",
        default=DEFAULT_DN_LEG,
        choices=sorted(DN_LEG_LABELS),
        help="ramp-down mapping leg (default: ramp-down-4c for full 0–4 °C overlap)",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    main(
        args.mlotst_up_dir,
        args.mlotst_dn_dir,
        args.mapping_dir,
        args.out,
        model=args.model,
        dn_leg=args.dn_leg,
    )
