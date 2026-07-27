"""Combined ramp-up + zero-emission-hold + ramp-down GMSAT trajectory, per model.

Exploratory QA figure — not part of the v1 GMD paper. Stitches all three mapping
products onto one shared calendar-year x-axis per model, using the ramp-up
file's start year as the zero point.

Usage::

    python exploratory/zehold/plot_trajectory.py --mapping-dir mapping
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl.io import model_label

EXPLORATORY_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPLORATORY_DIR.parents[1]
DEFAULT_MAPPING_DIR = REPO_ROOT / "mapping"
DEFAULT_OUT = EXPLORATORY_DIR / "figures" / "up_down_trajectory_preview.png"

UP_COLOR = "tab:red"
DN_COLOR_BY_HOLD = {2.0: "tab:blue", 4.0: "tab:cyan"}
DN_COLOR_FALLBACK = ["tab:blue", "tab:cyan", "tab:teal"]


def _dn_hold_target(path: Path) -> float:
    name = path.name.lower()
    if "gwl4p0" in name or "swl4p0" in name:
        return 4.0
    return 2.0


def _dn_color(target: float, fallback_used: dict) -> str:
    key = round(target, 2)
    if key in DN_COLOR_BY_HOLD:
        return DN_COLOR_BY_HOLD[key]
    if key not in fallback_used:
        idx = len(fallback_used) % len(DN_COLOR_FALLBACK)
        fallback_used[key] = DN_COLOR_FALLBACK[idx]
    return fallback_used[key]


def _dn_label(target: float) -> str:
    return f"ramp-down ({target:g}\N{DEGREE SIGN}C hold)"

ZE_COLOR_BY_TARGET = {2.0: "tab:orange", 4.0: "tab:brown"}
ZE_COLOR_FALLBACK = ["tab:olive", "tab:purple", "tab:pink", "tab:gray"]


def _leg_of(ds: xr.Dataset) -> str:
    return str(ds.attrs.get("leg", "ramp-up"))


def _discover_legs(mapping_dir: Path) -> dict[str, dict]:
    """Group every mapping file by canonical model id and leg."""
    by_model: dict[str, dict] = {}
    for p in sorted(mapping_dir.glob("gwlmap_*.nc")):
        with xr.open_dataset(p) as ds:
            mid = model_label(dict(ds.attrs))
            leg = _leg_of(ds)
        entry = by_model.setdefault(mid, {"up": None, "down": [], "ze": []})
        if leg == "ramp-down":
            entry["down"].append(p)
        elif leg == "ze-hold":
            entry["ze"].append(p)
        else:
            entry["up"] = p
    return {mid: e for mid, e in by_model.items() if e["up"] is not None}


def _ze_color(target_gwl: float, fallback_used: dict) -> str:
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
    ze_fallback: dict = {}
    dn_fallback: dict = {}

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
                color = _ze_color(target, ze_fallback)
                ze_targets_seen.add(round(target, 2) if np.isfinite(target) else -999.0)
                x_ze = ze["year"].values - up_year0
                ax.plot(x_ze, ze["gmsat_anomaly"].values, lw=0.7, alpha=0.35, color=color)
                ax.plot(
                    x_ze,
                    ze["gwl_axis"].values,
                    lw=1.8,
                    color=color,
                    label=f"ZE hold ({target:g}\N{DEGREE SIGN}C)",
                )
                y_min = min(y_min, float(np.nanmin(ze["gwl_axis"].values)))
                y_max = max(y_max, float(np.nanmax(ze["gwl_axis"].values)))

        for dn_path in sorted(entry["down"], key=_dn_hold_target):
            have_down = True
            target = _dn_hold_target(dn_path)
            color = _dn_color(target, dn_fallback)
            with xr.open_dataset(dn_path) as dn:
                x_dn = dn["year"].values - up_year0
                ax.plot(x_dn, dn["gmsat_anomaly"].values, lw=0.7, alpha=0.35, color=color)
                ax.plot(
                    x_dn,
                    dn["gwl_axis"].values,
                    lw=1.8,
                    color=color,
                    label=_dn_label(target),
                )
                y_min = min(y_min, float(np.nanmin(dn["gwl_axis"].values)))
                y_max = max(y_max, float(np.nanmax(dn["gwl_axis"].values)))

        ax.axhline(0.0, color="k", lw=0.6, alpha=0.2)
        ax.text(
            0.03,
            0.94,
            model,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=8,
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

    for ax in axes.flat[len(models) :]:
        ax.set_visible(False)
    for ax in axes.flat[: len(models)]:
        ax.set_ylim(y_min - 0.3, y_max + 0.3)

    gap_note = "gap = unmapped zero-emission hold"
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
