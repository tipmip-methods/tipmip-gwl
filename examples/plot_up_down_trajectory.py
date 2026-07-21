"""Combined ramp-up + zero-emission-hold + ramp-down GMSAT trajectory, per model.

Stitches all three mapping products (``product.build_mapping_dataset``,
``zehold.build_ze_mapping_dataset``, ``rampdown.build_rampdown_mapping_dataset``)
onto one shared calendar-year x-axis per model, using the ramp-up file's own
start year as the zero point -- all three legs are read from the same model's
internal calendar, so this is a direct alignment, not an inference.

A model needs only a ramp-up mapping file to be plotted; ramp-down and any
number of ZE-hold legs (e.g. gwl2p0 and gwl4p0) are overlaid whenever present.
The ZE-hold leg's gwl_axis is plotted as-is, non-monotonic and all -- unlike
the other two legs it is never forced onto a monotone axis, so a wobble in
the line is real signal (recalcitrant warming / zero-emissions commitment),
not a plotting artifact.

This is NOT a GWL-vs-GWL hysteresis diagram yet (that needs a second, physical
diagnostic variable, e.g. mlotst, resampled/relabelled through each leg's own
transform -- remap_to_gwl for ramp-up/ramp-down, relabel_to_gwl for ZE-hold,
since only the first two have a valid inverse to remap through). It's a
preview one level down: does the up-hold-down calendar story look right for
each model before building that.

Usage::

    python examples/plot_up_down_trajectory.py --mapping-dir mapping \\
        --out paper/figures/up_down_trajectory_preview.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl.io import model_label

DEFAULT_MAPPING_DIR = Path(__file__).resolve().parent.parent / "mapping"
DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent / "paper/figures/up_down_trajectory_preview.png"
)

UP_COLOR = "tab:red"
DN_COLOR = "tab:blue"
# ZE-hold colors keyed by nominal target GWL; unseen targets fall back to the cycle.
ZE_COLOR_BY_TARGET = {2.0: "tab:orange", 4.0: "tab:brown"}
ZE_COLOR_FALLBACK = ["tab:olive", "tab:purple", "tab:pink", "tab:gray"]


def _leg_of(ds: xr.Dataset) -> str:
    return str(ds.attrs.get("leg", "ramp-up"))


def _discover_legs(mapping_dir: Path) -> dict[str, dict]:
    """Group every mapping file by canonical model id and leg.

    Returns ``{model_id: {"up": path, "down": path|None, "ze": [paths]}}``.
    Uses ``model_id`` / staged filename tokens, not ``source_id``, so labels
    stay consistent when CMIP metadata differs (e.g. UKESM1-2-LL).
    """
    by_model: dict[str, dict] = {}
    for p in sorted(mapping_dir.glob("gwlmap_*.nc")):
        with xr.open_dataset(p) as ds:
            mid = model_label(dict(ds.attrs))
            leg = _leg_of(ds)
        entry = by_model.setdefault(mid, {"up": None, "down": None, "ze": []})
        if leg == "ramp-down":
            entry["down"] = p
        elif leg == "ze-hold":
            entry["ze"].append(p)
        else:
            entry["up"] = p
    return {mid: e for mid, e in by_model.items() if e["up"] is not None}


def _ze_color(target_gwl: float, fallback_used: dict) -> str:
    # NaN never equals itself, so a bare NaN dict key would silently pick a
    # new fallback color on every call -- route it through one shared bucket.
    key = "unparsed" if not np.isfinite(target_gwl) else round(target_gwl, 2)
    if key in ZE_COLOR_BY_TARGET:
        return ZE_COLOR_BY_TARGET[key]
    if key not in fallback_used:
        idx = len(fallback_used) % len(ZE_COLOR_FALLBACK)
        fallback_used[key] = ZE_COLOR_FALLBACK[idx]
    return fallback_used[key]


def main(mapping_dir=None, out=None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mapping_dir = Path(mapping_dir) if mapping_dir else DEFAULT_MAPPING_DIR
    out = Path(out) if out else DEFAULT_OUT

    legs = _discover_legs(mapping_dir)
    if not legs:
        raise SystemExit(f"No ramp-up mapping files found under {mapping_dir}")

    models = sorted(legs)
    ncol = 2
    nrow = int(np.ceil(len(models) / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(11, 2.3 * nrow), sharey=True, constrained_layout=True
    )

    y_min, y_max = np.inf, -np.inf
    have_down = False
    ze_targets_seen: set[float] = set()
    fallback_used: dict = {}

    for ax_idx, (ax, model) in enumerate(zip(axes.flat, models)):
        entry = legs[model]
        with xr.open_dataset(entry["up"]) as up:
            up_year0 = int(up["year"].values.min())
            x_up = up["year"].values - up_year0
            ax.plot(x_up, up["gmsat_anomaly"].values, lw=0.7, alpha=0.35, color=UP_COLOR)
            ax.plot(x_up, up["gwl_axis"].values, lw=1.8, color=UP_COLOR, label="ramp-up")
            y_min = min(y_min, float(np.nanmin(up["gwl_axis"].values)))
            y_max = max(y_max, float(np.nanmax(up["gwl_axis"].values)))

        for ze_path in sorted(entry["ze"]):
            with xr.open_dataset(ze_path) as ze:
                target = float(ze["target_gwl"].values)
                color = _ze_color(target, fallback_used)
                ze_targets_seen.add(round(target, 2) if np.isfinite(target) else -999.0)
                x_ze = ze["year"].values - up_year0
                ax.plot(x_ze, ze["gmsat_anomaly"].values, lw=0.7, alpha=0.35, color=color)
                ax.plot(
                    x_ze, ze["gwl_axis"].values, lw=1.8, color=color,
                    label=f"ZE hold ({target:g}\N{DEGREE SIGN}C)",
                )
                y_min = min(y_min, float(np.nanmin(ze["gwl_axis"].values)))
                y_max = max(y_max, float(np.nanmax(ze["gwl_axis"].values)))

        if entry["down"] is not None:
            have_down = True
            with xr.open_dataset(entry["down"]) as dn:
                x_dn = dn["year"].values - up_year0
                ax.plot(x_dn, dn["gmsat_anomaly"].values, lw=0.7, alpha=0.35, color=DN_COLOR)
                ax.plot(x_dn, dn["gwl_axis"].values, lw=1.8, color=DN_COLOR, label="ramp-down")
                y_min = min(y_min, float(np.nanmin(dn["gwl_axis"].values)))
                y_max = max(y_max, float(np.nanmax(dn["gwl_axis"].values)))

        ax.axhline(0.0, color="k", lw=0.6, alpha=0.2)
        ax.text(
            0.03, 0.94, model, transform=ax.transAxes, ha="left", va="top", fontsize=8,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.2),
        )

        row, col = divmod(ax_idx, ncol)
        if row == nrow - 1 and col == 0:
            ax.set_ylabel(r"GMSAT anomaly ($\degree$C)")
            ax.set_xlabel("Years since ramp-up start")
        if ax_idx == 0:
            handles, labels = ax.get_legend_handles_labels()
            uniq = dict(zip(labels, handles))
            ax.legend(
                uniq.values(), uniq.keys(), fontsize=7, loc="lower right", framealpha=0.7
            )

    for ax in axes.flat[len(models):]:
        ax.set_visible(False)
    for ax in axes.flat[: len(models)]:
        ax.set_ylim(y_min - 0.3, y_max + 0.3)

    gap_note = "gap = unmapped zero-emission hold" if not legs else "gaps: legs not staged for that model"
    if ze_targets_seen and have_down:
        gap_note = "any remaining gap = a ZE-hold target with no matching ramp-down leg staged"
    fig.suptitle(
        f"Ramp-up + ZE-hold + ramp-down GMSAT anomaly per model ({gap_note})",
        fontsize=10,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    path = main(args.mapping_dir, args.out)
    print(f"wrote {path}")
