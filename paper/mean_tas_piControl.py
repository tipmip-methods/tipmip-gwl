"""
piControl reference comparison: published 31-yr branch window vs full-run mean.

Same underlying comparison as baseline_sensitivity.py, plotted as a per-model
dot plot (this is the figure; baseline_sensitivity.py/table1.py are the text
tables backing the same numbers).

Usage::

    python paper/mean_tas_piControl.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

from tipmip_gwl.baseline import (
    branch_year_from_attrs,
    branch_window_reference,
    resolve_branch_year,
)
from tipmip_gwl.io import discover, load_gmsat_nc, read_attrs
from tipmip_gwl.mapping import picontrol_drift

from paper_style import model_color_map

plt.rcParams["figure.dpi"] = 300

BRANCH_WINDOW = 31
ROW_OFFSET = 0.17  # vertical offset between the two dots within each row
DEFAULT_OUT = (
    Path(__file__).resolve().parent / "figures" / "baseline_reference_comparison.png"
)


def _branch_reference(model, ru_path, pi_years, pi_gmsat, bi):
    """Return (31-yr branch mean, note, trailing) for one model.

    ``trailing`` is True when ``branch_window_reference`` uses the first
    ``BRANCH_WINDOW`` years of piControl because the centred window would start
    before the control record (ACCESS-ESM1-5, EC-Earth3-ESM-1).
    """
    if ru_path is None:
        return np.nan, "no ramp-up tas", False
    if bi.year is None:
        return np.nan, "missing branch year", False

    ru_years, _ = load_gmsat_nc(ru_path)
    try:
        branch, _ = resolve_branch_year(bi, model, ru_years, pi_years)
        if not (pi_years.min() <= branch <= pi_years.max()):
            return np.nan, "branch year out of range", False
        half = BRANCH_WINDOW // 2
        trailing = (branch - half) < float(pi_years.min())
        ref = branch_window_reference(
            pi_years,
            pi_gmsat,
            branch,
            window=BRANCH_WINDOW,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not contained in piControl" in msg or "no piControl data" in msg:
            note = "31-yr window out of range"
        else:
            note = "branch reference unavailable"
        return np.nan, note, False
    return ref, None, trailing


def main(up2p0_dir, picontrol_dir, out_path=None):
    pi_files = discover(picontrol_dir)
    ru_files = discover(up2p0_dir)

    means = []
    drifts = []
    branch_means = []
    branch_years = []
    branch_notes = []
    branch_trailing = []
    model_names = []

    for model in sorted(pi_files):
        pi_path = pi_files[model]
        pi_years, pi_gmsat = load_gmsat_nc(pi_path)
        means.append(float(np.mean(pi_gmsat)))
        drifts.append(picontrol_drift(pi_years, pi_gmsat)["drift_degC_per_century"])

        ru_path = ru_files.get(model)
        if ru_path is None:
            branch_means.append(np.nan)
            branch_years.append(None)
            branch_notes.append("no ramp-up tas")
            branch_trailing.append(False)
        else:
            bi = branch_year_from_attrs(read_attrs(ru_path))
            branch_years.append(bi.year)
            ref, note, trailing = _branch_reference(model, ru_path, pi_years, pi_gmsat, bi)
            branch_means.append(ref)
            branch_notes.append(note)
            branch_trailing.append(trailing)

        model_names.append(model)

    means = np.array(means)
    drifts = np.array(drifts)
    branch_means = np.array(branch_means)
    branch_years = np.array(branch_years, dtype=object)
    branch_notes = np.array(branch_notes, dtype=object)
    branch_trailing = np.array(branch_trailing, dtype=bool)
    model_names = np.array(model_names)
    diffs = means - branch_means

    sort_idx = np.argsort(means)
    means = means[sort_idx]
    branch_means = branch_means[sort_idx]
    branch_years = branch_years[sort_idx]
    branch_notes = branch_notes[sort_idx]
    branch_trailing = branch_trailing[sort_idx]
    drifts = drifts[sort_idx]
    diffs = diffs[sort_idx]
    model_names = model_names[sort_idx]
    colors = model_color_map(list(model_names))

    n = len(means)
    y = np.arange(n, dtype=float)
    y_full = y - ROW_OFFSET
    y_branch = y + ROW_OFFSET
    row_colors = ["#ffffff", "#ececec"]

    fig_h = 0.45 * n + 1.4
    fig = plt.figure(figsize=(12.5, fig_h))
    gs = GridSpec(1, 4, figure=fig, width_ratios=[0.4, 1.15, 0.85, 0.85], wspace=0.05)

    ax_names = fig.add_subplot(gs[0, 0])
    ax_means = fig.add_subplot(gs[0, 1], sharey=ax_names)
    ax_diff = fig.add_subplot(gs[0, 2], sharey=ax_names)
    ax_drift = fig.add_subplot(gs[0, 3], sharey=ax_names)

    data_axes = (ax_means, ax_diff, ax_drift)
    for ax in data_axes:
        ax.set_ylim(-0.5, n - 0.5)
        ax.invert_yaxis()
        for i in range(n):
            ax.axhspan(i - 0.5, i + 0.5, color=row_colors[i % 2], zorder=0)
        ax.grid(True, axis="x", color="0.75", linestyle="--", linewidth=0.8, zorder=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", left=False, labelleft=False)

    ax_names.set_ylim(-0.5, n - 0.5)
    ax_names.invert_yaxis()
    ax_names.axis("off")
    for i, (name, branch_year) in enumerate(zip(model_names, branch_years)):
        ax_names.axhspan(i - 0.5, i + 0.5, color=row_colors[i % 2], zorder=0)
        branch_label = (
            f"branch {branch_year}" if branch_year is not None else "branch —"
        )
        ax_names.text(
            1.0,
            i - 0.12,
            name,
            ha="right",
            va="center",
            fontsize=9,
            transform=ax_names.get_yaxis_transform(),
        )
        ax_names.text(
            1.0,
            i + 0.12,
            branch_label,
            ha="right",
            va="center",
            fontsize=7.5,
            color="0.45",
            transform=ax_names.get_yaxis_transform(),
        )

    ax_means.scatter(
        means,
        y_full,
        marker="o",
        c=[colors[name] for name in model_names],
        s=38,
        edgecolor="k",
        linewidth=0.5,
        zorder=3,
    )
    ax_means.scatter(
        branch_means,
        y_branch,
        marker="x",
        c=[colors[name] for name in model_names],
        s=38,
        linewidth=1.4,
        zorder=3,
    )
    x_pad = 0.06
    for i in range(n):
        if branch_trailing[i] and np.isfinite(branch_means[i]):
            ax_means.text(
                branch_means[i] - x_pad,
                y_branch[i],
                "trailing",
                ha="right",
                va="center",
                fontsize=8,
                color="k",
                zorder=3,
            )
        elif branch_notes[i] and not np.isfinite(branch_means[i]):
            ax_means.text(
                means[i],
                y_branch[i],
                branch_notes[i],
                ha="center",
                va="center",
                fontsize=8,
                color="k",
                zorder=3,
            )
    lo = np.nanmin([means, branch_means])
    hi = np.nanmax([means, branch_means])
    pad = 0.15
    ax_means.set_xlim(lo - pad, hi + pad)
    ax_means.set_xlabel("Mean GMSAT (K)", fontsize=10)
    ax_means.set_title("piControl reference", fontsize=11, pad=8)
    ax_means.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="k",
                markersize=7,
                label="Full piControl mean",
                markeredgecolor="none",
                linestyle="None",
            ),
            Line2D(
                [0],
                [0],
                marker="x",
                color="none",
                markeredgecolor="k",
                markersize=7,
                label=f"{BRANCH_WINDOW}-yr mean at branch",
                linewidth=1.4,
                linestyle="None",
            ),
        ],
        loc="lower left",
        fontsize=8,
        frameon=True,
        framealpha=0.9,
    )

    ok_diff = np.isfinite(diffs)
    ax_diff.scatter(
        diffs[ok_diff],
        y[ok_diff],
        c=[colors[name] for name in model_names[ok_diff]],
        s=42,
        edgecolor="k",
        linewidth=0.6,
        zorder=3,
    )
    ax_diff.set_xlabel("ΔGMSAT (K)", fontsize=10)
    ax_diff.set_title("Full − 31-yr branch", fontsize=11, pad=8)
    ax_diff.set_xlim(-0.12, 0.12)

    ax_drift.scatter(
        drifts,
        y,
        c=[colors[name] for name in model_names],
        s=42,
        edgecolor="k",
        linewidth=0.6,
        zorder=3,
    )
    ax_drift.set_xlabel("Drift (°C / century)", fontsize=10)
    ax_drift.set_title("Linear drift", fontsize=11, pad=8)
    ax_drift.set_xlim(-0.045, 0.045)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.12)
    out_path = Path(out_path) if out_path else DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="piControl reference comparison dot plot."
    )
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, out_path=args.out)
