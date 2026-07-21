"""
Zoomed illustration: relabel_to_gwl (native GWL axis) vs remap_to_gwl (0.02 °C grid).

Native points (circles) sit at each year's forward-mapped GWL, horizontal segments
show the lateral shift onto the nearest 0.02 °C grid line, and squares mark the
remapped values at those grid points. Uses the same raw annual-max mlotst as
:mod:`diagnostic_remap_demo`.

Usage::

    python paper/diagnostic_remap_binned_demo.py \\
        --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \\
        --mapping-dir mapping
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter

from tipmip_gwl.mapping import GWL_GRID_STEP, gwl_grid
from tipmip_gwl.product import relabel_to_gwl, remap_to_gwl

PAPER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PAPER_DIR))
import diagnostic_remap_demo as ddemo  # noqa: E402

DEFAULT_MODELS = ("GFDL-ESM2M", "MIROC-ES2L")
DEFAULT_OUT = PAPER_DIR / "figures" / "diagnostic_remap_binned_demo.png"
N_NATIVE = 6


def _load_series(model, mlotst_path, mapping_path):
    with xr.open_dataset(mlotst_path, decode_times=False) as ds:
        years_cal = ddemo._calendar_years(ds)
        vals = ddemo._area_weighted_global_mean(ds["mlotst"], ds[ddemo._lat_name(ds)])

    with xr.open_dataset(mapping_path) as mapping_ds:
        da = xr.DataArray(vals, dims=("time",), coords={"time": years_cal})
        relabelled = relabel_to_gwl(
            mapping_ds, da, year_dim="time", year_offset=0.0, new_dim="gwl"
        )
        binned = remap_to_gwl(mapping_ds, da, year_dim="time")

    binned_gwl = binned["gwl"].values.astype(float)
    binned_vals = binned.values.astype(float)
    return {
        "years": years_cal,
        "vals": vals,
        "gwl_native": relabelled["gwl"].values.astype(float),
        "binned_by_gwl": {
            float(g): float(v)
            for g, v in zip(binned_gwl, binned_vals)
            if np.isfinite(g) and np.isfinite(v)
        },
    }


def _pick_gwl_window(gwl_native, *, n_native=N_NATIVE, target_center=2.0):
    """Return (gwl_lo, gwl_hi) spanning ``n_native`` consecutive native points."""
    best = None
    for i in range(len(gwl_native) - n_native + 1):
        seg = gwl_native[i : i + n_native]
        if not np.all(np.isfinite(seg)):
            continue
        mid = 0.5 * (seg[0] + seg[-1])
        span = seg[-1] - seg[0]
        score = abs(mid - target_center) + max(0.0, span - 0.14) * 8.0
        if best is None or score < best[0]:
            best = (score, float(seg[0]), float(seg[-1]))
    if best is None:
        raise ValueError("could not find a finite native-GWL window")
    pad = GWL_GRID_STEP
    return best[1] - pad, best[2] + pad


def _nearest_grid(gwl: float) -> float:
    return float(np.round(gwl / GWL_GRID_STEP) * GWL_GRID_STEP)


def _gwl_axis_ticks(xlim: tuple[float, float]) -> np.ndarray:
    """0.02 °C tick positions aligned with the common GWL grid."""
    lo, hi = xlim
    start = np.ceil(lo / GWL_GRID_STEP - 1e-9) * GWL_GRID_STEP
    end = np.floor(hi / GWL_GRID_STEP + 1e-9) * GWL_GRID_STEP
    if end < start:
        return np.array([start])
    return np.arange(start, end + 0.5 * GWL_GRID_STEP, GWL_GRID_STEP)


def _plot(
    ax,
    series,
    models,
    *,
    gwl_lo,
    gwl_hi,
    grid_lines,
    styles,
    show_year_labels=True,
):
    """Native circles, horizontal shift, binned squares on the common grid."""
    x_vals: list[float] = []
    y_vals: list[float] = []

    for model, style in zip(models, styles):
        s = series[model]
        i0 = int(np.searchsorted(s["gwl_native"], gwl_lo, side="left"))
        i1 = int(np.searchsorted(s["gwl_native"], gwl_hi, side="right"))
        x_nat = s["gwl_native"][i0:i1]
        y_nat = s["vals"][i0:i1]
        years = s["years"][i0:i1]
        x_vals.extend(x_nat.tolist())
        y_vals.extend(y_nat.tolist())

        for x, y, yr in zip(x_nat, y_nat, years):
            x_snap = _nearest_grid(x)
            ax.plot(
                [x, x_snap],
                [y, y],
                color=style["color"],
                lw=1.2,
                alpha=0.55,
                zorder=1,
            )
            ax.scatter(
                x,
                y,
                s=72,
                facecolors="white",
                edgecolors=style["color"],
                marker="o",
                linewidth=1.4,
                zorder=3,
            )
            if show_year_labels:
                ax.annotate(
                    f"{int(yr)}",
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 8),
                    ha="center",
                    fontsize=7,
                    color=style["color"],
                    clip_on=False,
                )

        grid_in_window = grid_lines[(grid_lines >= gwl_lo) & (grid_lines <= gwl_hi)]
        x_vals.extend(grid_in_window.tolist())
        for g in grid_in_window:
            y_bin = s["binned_by_gwl"].get(float(g))
            if y_bin is None:
                continue
            y_vals.append(y_bin)
            ax.scatter(
                g,
                y_bin,
                s=72,
                color=style["color"],
                marker="s",
                edgecolor="k",
                linewidth=0.6,
                zorder=4,
            )

    x_lo, x_hi = min(x_vals), max(x_vals)
    y_lo, y_hi = min(y_vals), max(y_vals)
    x_span = x_hi - x_lo or GWL_GRID_STEP
    y_span = y_hi - y_lo or 1.0
    ax.set_xlim(x_lo - 0.05 * x_span, x_hi + 0.05 * x_span)
    ax.set_ylim(y_lo - 0.10 * y_span, y_hi + 0.16 * y_span)

    x_ticks = _gwl_axis_ticks(ax.get_xlim())
    ax.set_xticks(x_ticks)
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    for g in x_ticks:
        ax.axvline(g, color="0.86", lw=0.9, zorder=0)
    ax.set_xlabel("GWL (°C)")
    ax.set_ylabel("Global-mean annual-max mixed-layer depth (m)")

    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="0.3",
            markerfacecolor="white",
            markeredgecolor="0.3",
            markeredgewidth=1.4,
            lw=0,
            label="relabel_to_gwl (native axis)",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="0.3",
            markerfacecolor="0.3",
            markeredgecolor="k",
            markersize=7,
            lw=0,
            label="remap_to_gwl (common grid)",
        ),
        Line2D([0], [0], color="0.5", lw=1.2, label="shift onto grid"),
    ]
    for model, style in zip(models, styles):
        handles.append(Line2D([0], [0], color=style["color"], lw=2, label=model))
    ax.legend(handles=handles, loc="center right", fontsize=7.5, framealpha=0.92)


def main(
    mlotst_dir,
    mapping_dir,
    out_path,
    *,
    models=DEFAULT_MODELS,
    n_native=N_NATIVE,
    target_gwl=2.0,
    show_year_labels=True,
):
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)
    mlotst_files = ddemo._discover_native_mlotst(mlotst_dir)
    mapping_files = ddemo._mapping_index_by_rampup_model(mapping_dir)

    models = tuple(models)
    missing = [m for m in models if m not in mlotst_files or m not in mapping_files]
    if missing:
        raise SystemExit(f"models not available on disk: {missing}")

    series = {m: _load_series(m, mlotst_files[m], mapping_files[m]) for m in models}
    gwl_lo, gwl_hi = _pick_gwl_window(
        series[models[0]]["gwl_native"], n_native=n_native, target_center=target_gwl
    )
    grid_lines = gwl_grid(GWL_GRID_STEP, gwl_max=gwl_hi + GWL_GRID_STEP)

    palette = plt.cm.Dark2.colors
    styles = [
        dict(color=palette[i % len(palette)], label=m) for i, m in enumerate(models)
    ]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    _plot(
        ax,
        series,
        models,
        gwl_lo=gwl_lo,
        gwl_hi=gwl_hi,
        grid_lines=grid_lines,
        styles=styles,
        show_year_labels=show_year_labels,
    )
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"Saved {out_path}")
    print(f"  GWL window: [{gwl_lo:.3f}, {gwl_hi:.3f}] °C")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Zoomed relabel_to_gwl vs remap_to_gwl illustration."
    )
    parser.add_argument("--mlotst-dir", required=True)
    parser.add_argument("--mapping-dir", default="mapping")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="one or two models (default: GFDL-ESM2M MIROC-ES2L)",
    )
    parser.add_argument("--n-native", type=int, default=N_NATIVE)
    parser.add_argument(
        "--target-gwl",
        type=float,
        default=2.0,
        help="centre the zoom window near this GWL (°C)",
    )
    parser.add_argument(
        "--no-year-labels",
        action="store_true",
        help="omit calendar-year labels on native points",
    )
    args = parser.parse_args()
    main(
        args.mlotst_dir,
        args.mapping_dir,
        args.out,
        models=args.models,
        n_native=args.n_native,
        target_gwl=args.target_gwl,
        show_year_labels=not args.no_year_labels,
    )
