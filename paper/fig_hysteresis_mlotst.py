"""Path-dependence demo: SPG mixed-layer depth and polar sea-ice volume vs GWL.

Three horizontal panels (ramp-up vs ramp-down from 4 °C on the shared 0.02 °C
grid, 0–4 °C):

(a) GFDL-ESM2M — SPG regional-mean annual-max mixed-layer depth
(b) UKESM1-2-LL — Arctic sea-ice volume per area
(c) UKESM1-2-LL — Antarctic sea-ice volume per area

Usage::

    python paper/fig_hysteresis_mlotst.py \\
        --mlotst-up-dir ~/data/tipmip/mlotst/esm-up2p0 \\
        --mlotst-dn-dir ~/data/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0 \\
        --sivol-up-dir ~/data/tipmip/sivol/esm-up2p0 \\
        --sivol-dn-dir ~/data/tipmip/sivol/esm-up2p0-gwl4p0-50y-dn2p0 \\
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
from helper_mlotst_remap import calendar_years, discover_native_mlotst, mapping_index_by_leg
from helper_paper_style import model_color_map
from helper_region_inset import add_antarctic_inset, add_arctic_inset, add_spg_inset
from helper_regional_diagnostics import (
    discover_sivol,
    open_sivol_timeseries,
    spg_mlotst_timeseries,
)

from tipmip_gwl.mapping import GWL_GRID_STEP
from tipmip_gwl.product import resample_to_gwl

PAPER_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = PAPER_DIR / "figures" / "fig_hysteresis_mlotst_dn4c.png"
DEFAULT_MLOTST_MODEL = "GFDL-ESM2M"
DEFAULT_SIVOL_MODEL = "UKESM1-2-LL"
DEFAULT_DN_LEG = "ramp-down-4c"
GWL_MIN = 0.0
GWL_MAX = 4.0

DN_LEG_LABELS = {
    "ramp-down-2c": "Ramp-down from 2 °C",
    "ramp-down-4c": "Ramp-down from 4 °C",
}


def _resample_diagnostic(
    years_cal: np.ndarray,
    values: np.ndarray,
    mapping_path: Path,
    *,
    gwl_max: float = GWL_MAX,
) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(mapping_path) as mapping_ds:
        da = xr.DataArray(values, dims=("time",), coords={"time": years_cal})
        resampled = resample_to_gwl(
            mapping_ds,
            da,
            year_dim="time",
            gwl_min=GWL_MIN,
            gwl_max=gwl_max,
            gwl_step=GWL_GRID_STEP,
        )
    return resampled["gwl"].values.astype(float), resampled.values.astype(float)


def _load_mlotst_spg(
    mlotst_path: Path,
    mapping_path: Path,
    *,
    gwl_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(mlotst_path, decode_times=False) as ds:
        years_cal = calendar_years(ds)
        regional = spg_mlotst_timeseries(ds)
    return _resample_diagnostic(years_cal, regional, mapping_path, gwl_max=gwl_max)


def _load_sivol_polar(
    sivol_path: Path,
    mapping_path: Path,
    *,
    hemisphere: str,
    gwl_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    years_cal, regional = open_sivol_timeseries(sivol_path, hemisphere=hemisphere)
    return _resample_diagnostic(years_cal, regional, mapping_path, gwl_max=gwl_max)


def _plot_leg(
    ax,
    gwl: np.ndarray,
    vals_up: np.ndarray,
    vals_dn: np.ndarray,
    *,
    color: str,
    dn_label: str,
    ylabel: str,
    title: str,
    panel_label: str,
    gwl_max: float,
    model_note: str | None = None,
    show_legend: bool = False,
    legend_loc: str = "upper right",
) -> None:
    up_mask = np.isfinite(vals_up)
    dn_mask = np.isfinite(vals_dn)
    ax.plot(gwl[up_mask], vals_up[up_mask], color=color, lw=2.2, label="Ramp-up")
    ax.plot(gwl[dn_mask], vals_dn[dn_mask], color=color, lw=1.0, label=dn_label)
    ax.set_xlim(GWL_MIN, gwl_max)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=6)
    ax.text(
        0.02,
        0.98,
        panel_label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        fontweight="bold",
    )
    if model_note:
        ax.text(
            1.0,
            1.02,
            model_note,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="0.35",
            clip_on=False,
        )
    if show_legend:
        ax.legend(framealpha=0, loc=legend_loc)


def main(
    mlotst_up_dir,
    mlotst_dn_dir,
    sivol_up_dir,
    sivol_dn_dir,
    mapping_dir,
    out_path=DEFAULT_OUT,
    *,
    mlotst_model: str = DEFAULT_MLOTST_MODEL,
    sivol_model: str = DEFAULT_SIVOL_MODEL,
    dn_leg: str = DEFAULT_DN_LEG,
) -> Path:
    mlotst_up_dir = Path(mlotst_up_dir)
    mlotst_dn_dir = Path(mlotst_dn_dir)
    sivol_up_dir = Path(sivol_up_dir)
    sivol_dn_dir = Path(sivol_dn_dir)
    mapping_dir = Path(mapping_dir)

    if dn_leg not in DN_LEG_LABELS:
        raise SystemExit(
            f"Unknown dn_leg {dn_leg!r}; choose from {sorted(DN_LEG_LABELS)}"
        )

    gwl_max = GWL_MAX if dn_leg == "ramp-down-4c" else 3.0
    dn_label = DN_LEG_LABELS[dn_leg]

    up_mlotst = discover_native_mlotst(mlotst_up_dir)
    dn_mlotst = discover_native_mlotst(mlotst_dn_dir)
    up_sivol = discover_sivol(sivol_up_dir)
    dn_sivol = discover_sivol(sivol_dn_dir)
    up_maps = mapping_index_by_leg(mapping_dir, "ramp-up")
    dn_maps = mapping_index_by_leg(mapping_dir, dn_leg)

    for label, model, up_idx, dn_idx in (
        ("mlotst", mlotst_model, up_mlotst, dn_mlotst),
        ("sivol", sivol_model, up_sivol, dn_sivol),
    ):
        if model not in up_idx or model not in dn_idx:
            raise SystemExit(f"Model {model!r} not found in both {label} directories")
        if model not in up_maps or model not in dn_maps:
            raise SystemExit(f"No ramp-up / {dn_leg!r} mapping for {model!r}")

    mlotst_color = model_color_map([mlotst_model])[mlotst_model]
    sivol_color = model_color_map([sivol_model])[sivol_model]

    gwl_spg, mlotst_up = _load_mlotst_spg(
        up_mlotst[mlotst_model], up_maps[mlotst_model], gwl_max=gwl_max
    )
    gwl_spg_dn, mlotst_dn = _load_mlotst_spg(
        dn_mlotst[mlotst_model], dn_maps[mlotst_model], gwl_max=gwl_max
    )
    if not np.allclose(gwl_spg, gwl_spg_dn, equal_nan=True):
        raise RuntimeError("SPG: ramp-up and ramp-down resampling grids differ")

    gwl_arc, sivol_arc_up = _load_sivol_polar(
        up_sivol[sivol_model],
        up_maps[sivol_model],
        hemisphere="arctic",
        gwl_max=gwl_max,
    )
    gwl_arc_dn, sivol_arc_dn = _load_sivol_polar(
        dn_sivol[sivol_model],
        dn_maps[sivol_model],
        hemisphere="arctic",
        gwl_max=gwl_max,
    )
    if not np.allclose(gwl_arc, gwl_arc_dn, equal_nan=True):
        raise RuntimeError("Arctic sivol: ramp-up and ramp-down grids differ")

    gwl_ant, sivol_ant_up = _load_sivol_polar(
        up_sivol[sivol_model],
        up_maps[sivol_model],
        hemisphere="antarctic",
        gwl_max=gwl_max,
    )
    gwl_ant_dn, sivol_ant_dn = _load_sivol_polar(
        dn_sivol[sivol_model],
        dn_maps[sivol_model],
        hemisphere="antarctic",
        gwl_max=gwl_max,
    )
    if not np.allclose(gwl_ant, gwl_ant_dn, equal_nan=True):
        raise RuntimeError("Antarctic sivol: ramp-up and ramp-down grids differ")

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), sharex=True, constrained_layout=True)

    _plot_leg(
        axes[0],
        gwl_spg,
        mlotst_up,
        mlotst_dn,
        color=mlotst_color,
        dn_label=dn_label,
        ylabel="Mixed-layer depth (m)",
        title="Subpolar Gyre",
        model_note=mlotst_model,
        panel_label="(a)",
        gwl_max=gwl_max,
    )
    add_spg_inset(axes[0], outline_color=mlotst_color)
    _plot_leg(
        axes[1],
        gwl_arc,
        sivol_arc_up,
        sivol_arc_dn,
        color=sivol_color,
        dn_label=dn_label,
        ylabel="Sea-ice volume (m)",
        title="Arctic cap",
        model_note=sivol_model,
        panel_label="(b)",
        gwl_max=gwl_max,
    )
    add_arctic_inset(axes[1], outline_color=sivol_color)
    _plot_leg(
        axes[2],
        gwl_ant,
        sivol_ant_up,
        sivol_ant_dn,
        color=sivol_color,
        dn_label=dn_label,
        ylabel="Sea-ice volume (m)",
        title="Antarctic cap",
        model_note=sivol_model,
        panel_label="(c)",
        gwl_max=gwl_max,
        show_legend=True,
        legend_loc="lower left",
    )
    add_antarctic_inset(axes[2], outline_color=sivol_color)

    for ax in axes:
        ax.set_xlabel("GWL (°C)")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(
        f"Saved {out_path} "
        f"(mlotst={mlotst_model}, sivol={sivol_model}; {dn_leg}; resample_to_gwl)"
    )
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mlotst-up-dir", required=True)
    parser.add_argument("--mlotst-dn-dir", required=True)
    parser.add_argument("--sivol-up-dir", required=True)
    parser.add_argument("--sivol-dn-dir", required=True)
    parser.add_argument("--mapping-dir", default="mapping")
    parser.add_argument("--mlotst-model", default=DEFAULT_MLOTST_MODEL)
    parser.add_argument("--sivol-model", default=DEFAULT_SIVOL_MODEL)
    parser.add_argument(
        "--dn-leg",
        default=DEFAULT_DN_LEG,
        choices=sorted(DN_LEG_LABELS),
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    main(
        args.mlotst_up_dir,
        args.mlotst_dn_dir,
        args.sivol_up_dir,
        args.sivol_dn_dir,
        args.mapping_dir,
        args.out,
        mlotst_model=args.mlotst_model,
        sivol_model=args.sivol_model,
        dn_leg=args.dn_leg,
    )
