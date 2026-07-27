"""Side-by-side hysteresis figure variants (B vs C).

B — zoomed exemplar models (0–3 °C) plus |dn − up| at shared GWL.
C — same layout as the original all-model plot, but with a lightly smoothed
    global-mean series before relabel (σ = 3 yr; only annual-max mlotst staged).

Outputs ``paper/figures/hysteresis_compare_B.png``,
``hysteresis_compare_C.png``, and ``hysteresis_compare_BC.png``.

Usage::

    python paper/plot_hysteresis_compare.py \\
        --mlotst-up-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \\
        --mlotst-dn-dir ~/Desktop/tipmip/mlotst/esm-up2p0-gwl2p0-50y-dn2p0 \\
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
from scipy.ndimage import gaussian_filter1d

from mlotst_remap_helpers import (
    area_weighted_global_mean,
    calendar_years,
    discover_native_mlotst,
    lat_name,
    mapping_index_by_leg,
)
from paper_style import model_color_map
from tipmip_gwl.product import relabel_to_gwl

PAPER_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = PAPER_DIR / "figures"

GWL_XLIM = (0.0, 3.0)
EXEMPLARS = ("ACCESS-ESM1-5", "GISS-E2-1-G-CC2", "UKESM1-2-LL")
SMOOTH_SIGMA_YR = 3.0
DELTA_GWL = np.arange(0.0, 2.51, 0.05)


def _global_mean_series(mlotst_path: Path) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(mlotst_path, decode_times=False) as ds:
        years = calendar_years(ds)
        gmean = area_weighted_global_mean(ds["mlotst"], ds[lat_name(ds)])
    return years, gmean


def _relabel_on_gwl(
    years: np.ndarray,
    values: np.ndarray,
    mapping_path: Path,
    *,
    smooth_sigma_yr: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    vals = values.astype(float)
    if smooth_sigma_yr > 0:
        vals = gaussian_filter1d(vals, sigma=smooth_sigma_yr)
    with xr.open_dataset(mapping_path) as mapping_ds:
        da = xr.DataArray(vals, dims=("time",), coords={"time": years})
        relabeled = relabel_to_gwl(mapping_ds, da, year_dim="time", new_dim="gwl")
    gwl = relabeled["gwl"].values.astype(float)
    order = np.argsort(gwl)
    return gwl[order], relabeled.values[order]


def _interp_at(gwl: np.ndarray, vals: np.ndarray, targets: np.ndarray) -> np.ndarray:
    out = np.full(targets.shape, np.nan, dtype=float)
    mask = np.isfinite(gwl) & np.isfinite(vals)
    if mask.sum() < 2:
        return out
    out[:] = np.interp(targets, gwl[mask], vals[mask], left=np.nan, right=np.nan)
    return out


def _load_all_series(
    models: list[str],
    up_mlotst: dict[str, Path],
    dn_mlotst: dict[str, Path],
    up_maps: dict[str, Path],
    dn_maps: dict[str, Path],
    *,
    smooth_sigma_yr: float = 0.0,
) -> dict[str, dict[str, np.ndarray]]:
    out: dict[str, dict[str, np.ndarray]] = {}
    for model in models:
        years_up, gmean_up = _global_mean_series(up_mlotst[model])
        years_dn, gmean_dn = _global_mean_series(dn_mlotst[model])
        gwl_up, vals_up = _relabel_on_gwl(
            years_up, gmean_up, up_maps[model], smooth_sigma_yr=smooth_sigma_yr
        )
        gwl_dn, vals_dn = _relabel_on_gwl(
            years_dn, gmean_dn, dn_maps[model], smooth_sigma_yr=smooth_sigma_yr
        )
        out[model] = dict(gwl_up=gwl_up, vals_up=vals_up, gwl_dn=gwl_dn, vals_dn=vals_dn)
    return out


def _plot_up_dn(ax, gwl: np.ndarray, vals: np.ndarray, *, color: str, label: str, dashed: bool) -> None:
    ax.plot(
        gwl,
        vals,
        color=color,
        lw=1.8,
        ls="--" if dashed else "-",
        label=label,
    )


def plot_variant_b(
    series: dict[str, dict[str, np.ndarray]],
    models: list[str],
    colors: dict[str, str],
    out_path: Path,
) -> None:
    fig, (ax_ex, ax_delta) = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)

    for model in EXEMPLARS:
        if model not in series:
            continue
        c = colors[model]
        d = series[model]
        _plot_up_dn(ax_ex, d["gwl_up"], d["vals_up"], color=c, label=f"{model} (up)", dashed=False)
        _plot_up_dn(ax_ex, d["gwl_dn"], d["vals_dn"], color=c, label=f"{model} (down)", dashed=True)

    ax_ex.set_xlim(*GWL_XLIM)
    ax_ex.set_xlabel("GWL (°C)")
    ax_ex.set_ylabel("Global-mean annual-max mixed-layer depth (m)")
    ax_ex.set_title("(B1) Exemplar models", loc="left", fontsize=11, fontweight="bold")
    ax_ex.legend(fontsize=8, framealpha=0.9, loc="upper right")

    for model in models:
        d = series[model]
        up_at = _interp_at(d["gwl_up"], d["vals_up"], DELTA_GWL)
        dn_at = _interp_at(d["gwl_dn"], d["vals_dn"], DELTA_GWL)
        delta = dn_at - up_at
        ax_delta.plot(DELTA_GWL, delta, color=colors[model], lw=1.3, label=model)

    ax_delta.axhline(0.0, color="k", lw=0.6, alpha=0.25)
    ax_delta.set_xlim(*GWL_XLIM)
    ax_delta.set_xlabel("GWL (°C)")
    ax_delta.set_ylabel(r"$\Delta$ mixed-layer depth (down $-$ up, m)")
    ax_delta.set_title("(B2) Path dependence", loc="left", fontsize=11, fontweight="bold")
    ax_delta.legend(ncol=2, fontsize=7, framealpha=0.9, loc="upper right")

    fig.suptitle(
        "Option B: zoom + exemplars + signed gap at shared GWL",
        fontsize=12,
        y=1.02,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_variant_c(
    series: dict[str, dict[str, np.ndarray]],
    models: list[str],
    colors: dict[str, str],
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)

    for model in models:
        c = colors[model]
        d = series[model]
        _plot_up_dn(ax, d["gwl_up"], d["vals_up"], color=c, label=f"{model} (up)", dashed=False)
        _plot_up_dn(ax, d["gwl_dn"], d["vals_dn"], color=c, label=f"{model} (down)", dashed=True)

    ax.set_xlim(*GWL_XLIM)
    ax.set_xlabel("GWL (°C)")
    ax.set_ylabel("Global-mean annual-max mixed-layer depth (m)")
    ax.set_title(
        f"Option C: all models, Gaussian-smoothed ({SMOOTH_SIGMA_YR:g} yr) before relabel",
        fontsize=11,
    )
    ax.legend(ncol=2, fontsize=7, framealpha=0.85, loc="upper right")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_side_by_side(
    series_b: dict[str, dict[str, np.ndarray]],
    series_c: dict[str, dict[str, np.ndarray]],
    models: list[str],
    colors: dict[str, str],
    out_path: Path,
) -> None:
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1.0], hspace=0.28, wspace=0.22)

    ax_b1 = fig.add_subplot(gs[0, 0])
    ax_b2 = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])

    for model in EXEMPLARS:
        if model not in series_b:
            continue
        c = colors[model]
        d = series_b[model]
        _plot_up_dn(ax_b1, d["gwl_up"], d["vals_up"], color=c, label=f"{model} (up)", dashed=False)
        _plot_up_dn(ax_b1, d["gwl_dn"], d["vals_dn"], color=c, label=f"{model} (down)", dashed=True)

    ax_b1.set_xlim(*GWL_XLIM)
    ax_b1.set_ylabel("Mixed-layer depth (m)")
    ax_b1.set_title("B — exemplar models (0–3 °C)", loc="left", fontweight="bold")
    ax_b1.legend(fontsize=8, loc="upper right")

    for model in models:
        d = series_b[model]
        up_at = _interp_at(d["gwl_up"], d["vals_up"], DELTA_GWL)
        dn_at = _interp_at(d["gwl_dn"], d["vals_dn"], DELTA_GWL)
        ax_b2.plot(DELTA_GWL, dn_at - up_at, color=colors[model], lw=1.3, label=model)

    ax_b2.axhline(0.0, color="k", lw=0.6, alpha=0.25)
    ax_b2.set_xlim(*GWL_XLIM)
    ax_b2.set_title("B — down minus up at shared GWL", loc="left", fontweight="bold")
    ax_b2.legend(ncol=2, fontsize=7, loc="upper right")

    for model in models:
        c = colors[model]
        d = series_c[model]
        _plot_up_dn(ax_c, d["gwl_up"], d["vals_up"], color=c, label=f"{model} (up)", dashed=False)
        _plot_up_dn(ax_c, d["gwl_dn"], d["vals_dn"], color=c, label=f"{model} (down)", dashed=True)

    ax_c.set_xlim(*GWL_XLIM)
    ax_c.set_xlabel("GWL (°C)")
    ax_c.set_ylabel("Mixed-layer depth (m)")
    ax_c.set_title(
        f"C — all models, {SMOOTH_SIGMA_YR:g}-yr Gaussian smooth before relabel (0–3 °C)",
        loc="left",
        fontweight="bold",
    )
    ax_c.legend(ncol=4, fontsize=7, loc="upper right")

    fig.suptitle("Hysteresis figure variants (annual-max mlotst, ramp-down from 2 °C hold)", y=0.98)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(
    mlotst_up_dir,
    mlotst_dn_dir,
    mapping_dir,
    out_dir=DEFAULT_OUT_DIR,
) -> tuple[Path, Path, Path]:
    mlotst_up_dir = Path(mlotst_up_dir)
    mlotst_dn_dir = Path(mlotst_dn_dir)
    mapping_dir = Path(mapping_dir)
    out_dir = Path(out_dir)

    up_mlotst = discover_native_mlotst(mlotst_up_dir)
    dn_mlotst = discover_native_mlotst(mlotst_dn_dir)
    up_maps = mapping_index_by_leg(mapping_dir, "ramp-up")
    dn_maps = mapping_index_by_leg(mapping_dir, "ramp-down-2c")
    models = sorted(set(up_mlotst) & set(dn_mlotst) & set(up_maps) & set(dn_maps))
    colors = model_color_map(models)

    series_b = _load_all_series(
        models, up_mlotst, dn_mlotst, up_maps, dn_maps, smooth_sigma_yr=0.0
    )
    series_c = _load_all_series(
        models, up_mlotst, dn_mlotst, up_maps, dn_maps, smooth_sigma_yr=SMOOTH_SIGMA_YR
    )

    out_b = out_dir / "hysteresis_compare_B.png"
    out_c = out_dir / "hysteresis_compare_C.png"
    out_bc = out_dir / "hysteresis_compare_BC.png"

    plot_variant_b(series_b, models, colors, out_b)
    plot_variant_c(series_c, models, colors, out_c)
    plot_side_by_side(series_b, series_c, models, colors, out_bc)

    print(f"Saved {out_b}")
    print(f"Saved {out_c}")
    print(f"Saved {out_bc}")
    return out_b, out_c, out_bc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mlotst-up-dir", required=True)
    parser.add_argument("--mlotst-dn-dir", required=True)
    parser.add_argument("--mapping-dir", default="mapping")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    main(args.mlotst_up_dir, args.mlotst_dn_dir, args.mapping_dir, args.out_dir)
