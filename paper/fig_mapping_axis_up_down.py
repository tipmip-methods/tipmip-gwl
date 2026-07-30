"""Ramp-up and ramp-down monotone GWL axes (Methods figure).

Two-panel figure: (a) ramp-up; (b) both ramp-down legs overlaid in GWL space
(same line styles; two branch labels only). Thin lines = unsmoothed GMSAT
anomaly; thick lines = monotone ``gwl_axis``.

Usage::

    python paper/fig_mapping_axis_up_down.py --mapping-dir mapping
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from helper_mlotst_remap import bundled_models, mapping_index_by_leg
from helper_paper_style import model_color_map

PAPER_DIR = Path(__file__).resolve().parent
DEFAULT_MAPPING_DIR = PAPER_DIR.parent / "mapping"
DEFAULT_OUT = PAPER_DIR / "figures" / "fig_mapping_axis_up_down.png"

GWL_YLIM = (-1.5, 4.5)
RAMP_UP_XLIM = (-5, 220)
PROTOCOL_RATE = 0.02  # °C yr⁻¹ (2 °C century⁻¹)

DN_BRANCH_LABELS: tuple[tuple[str, str, tuple[float, float]], ...] = (
    ("ramp-down-2c", "from 2 °C", (10.0, 2.3)),
    ("ramp-down-4c", "from 4 °C", (70.0, 3.6)),
)


def _gwl_reference_lines(ax) -> None:
    for gwl in (0.0, 2.0, 4.0):
        ax.axhline(gwl, color="k", lw=0.6, alpha=0.2, zorder=1)


def _plot_maps(
    ax,
    maps: dict[str, Path],
    colors: dict[str, str],
    *,
    legend: bool = False,
) -> float:
    """Plot one mapping leg; return max time extent."""
    t_max = 0.0
    for model in sorted(maps):
        color = colors[model]
        with xr.open_dataset(maps[model]) as ds:
            years = np.asarray(ds["year"].values, dtype=float)
            t = years - years[0]
            anom = np.asarray(ds["gmsat_anomaly"].values, dtype=float)
            axis = np.asarray(ds["gwl_axis"].values, dtype=float)
        if t.size == 0:
            continue
        t_max = max(t_max, float(t[-1]))
        label = model if legend else None
        ax.plot(t, axis, lw=2.2, color=color, label=label, zorder=3)
        ax.plot(t, anom, lw=0.8, alpha=0.35, color=color, zorder=2)
    return t_max


def _plot_rampdown_panel(
    ax,
    dn_by_leg: dict[str, dict[str, Path]],
    colors: dict[str, str],
    models: list[str],
) -> float:
    """Overlay ramp-down legs; annotate each branch once in GWL space."""
    t_max = 0.0
    for leg, _branch_label, _label_xy in DN_BRANCH_LABELS:
        if leg not in dn_by_leg:
            continue
        maps = {m: dn_by_leg[leg][m] for m in models if m in dn_by_leg[leg]}
        t_max = max(t_max, _plot_maps(ax, maps, colors))

    _gwl_reference_lines(ax)
    ax.set_xlabel("Years since ramp-down start")
    ax.set_title("(b) Ramp-down", loc="left", fontsize=11, fontweight="bold")

    for leg, branch_label, (tx, ty) in DN_BRANCH_LABELS:
        if leg not in dn_by_leg:
            continue
        ax.text(
            tx,
            ty,
            branch_label,
            ha="left",
            va="center",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.2),
            zorder=4,
        )

    return t_max


def main(
    mapping_dir=None,
    out_path=None,
    *,
    dn_legs: tuple[str, ...] = ("ramp-down-2c", "ramp-down-4c"),
) -> Path:
    mapping_dir = Path(mapping_dir) if mapping_dir else DEFAULT_MAPPING_DIR
    out_path = Path(out_path) if out_path else DEFAULT_OUT

    up_maps = mapping_index_by_leg(mapping_dir, "ramp-up")
    if not up_maps:
        raise SystemExit(f"No ramp-up mapping files found under {mapping_dir}")

    dn_by_leg: dict[str, dict[str, Path]] = {}
    for leg in dn_legs:
        maps = mapping_index_by_leg(mapping_dir, leg)
        if maps:
            dn_by_leg[leg] = maps
        else:
            print(f"note: no {leg!r} mappings under {mapping_dir}; skipping")

    if not dn_by_leg:
        raise SystemExit(f"No ramp-down mapping files found under {mapping_dir}")

    models = bundled_models(up_maps, *dn_by_leg.values())
    if not models:
        raise SystemExit("No bundled models with ramp-up and at least one ramp-down mapping")

    colors = model_color_map(models)
    up_maps = {m: up_maps[m] for m in models}

    fig, (ax_up, ax_dn) = plt.subplots(
        1, 2, figsize=(12, 5.5), sharey=True, constrained_layout=True
    )

    t_up = _plot_maps(ax_up, up_maps, colors, legend=True)
    _gwl_reference_lines(ax_up)
    xs = np.array([0.0, min(t_up, 4.0 / PROTOCOL_RATE)])
    ax_up.plot(
        xs,
        PROTOCOL_RATE * xs,
        color="0.3",
        ls="--",
        lw=1.2,
        label="2 °C/century",
        zorder=1,
    )
    ax_up.set_xlabel("Years since ramp-up start")
    ax_up.set_title("(a) Ramp-up", loc="left", fontsize=11, fontweight="bold")

    t_dn = _plot_rampdown_panel(ax_dn, dn_by_leg, colors, models)

    ax_up.set_ylabel(r"GWL ($\degree$C)")
    ax_up.set_ylim(*GWL_YLIM)
    ax_up.set_xlim(*RAMP_UP_XLIM)
    if t_dn > 0:
        ax_dn.set_xlim(-2, t_dn + 5)

    handles, labels = ax_up.get_legend_handles_labels()
    ax_up.legend(
        handles,
        labels,
        ncol=3,
        framealpha=0.0,
        loc="lower left",
        bbox_to_anchor=(0.025, 0.025),
        fontsize=8,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    dn_note = ", ".join(sorted(dn_by_leg))
    print(f"Saved {out_path} ({len(models)} models; ramp-down legs: {dn_note})")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--dn-legs",
        nargs="*",
        default=["ramp-down-2c", "ramp-down-4c"],
        choices=("ramp-down-2c", "ramp-down-4c"),
        help="ramp-down legs to overlay (default: both Tier-1 legs)",
    )
    args = parser.parse_args()
    main(args.mapping_dir, args.out, dn_legs=tuple(args.dn_legs))
