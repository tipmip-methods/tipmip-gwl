"""
plotting.py
===========
Diagnostic figures for the time->GWL mapping. Both functions take the list of
``ModelDiag`` records produced by :func:`tipmip_gwl.diagnostics.run_diagnostics`
(only their attributes are used, so there is no import dependency on the driver).

Matplotlib is imported lazily so the rest of the package has no hard dependency
on it; install with the ``plot`` extra to use these.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

GWL_PLOT_LO = 0.0
GWL_PLOT_HI = 4.0
GWL_YLIM = (-0.2, 4.2)


def _trim_to_gwl_window(t, *series, lo=GWL_PLOT_LO, hi=GWL_PLOT_HI):
    """Keep the contiguous segment where the first series lies in ``[lo, hi]``."""
    t = np.asarray(t, float)
    ref = np.asarray(series[0], float)
    in_range = (ref >= lo) & (ref <= hi)
    if not in_range.any():
        empty = t[:0]
        return (empty,) + tuple(np.asarray(s, float)[:0] for s in series)
    i0, i1 = np.where(in_range)[0][[0, -1]]
    sl = slice(int(i0), int(i1) + 1)
    return (t[sl],) + tuple(np.asarray(s, float)[sl] for s in series)


def plot_diagnostics(diags, outdir):
    """Two diagnostic figures written to ``outdir``:

    rampup_anomaly.png   -- ramp-up GWL vs years-since-start (0--4 degC window),
        all models overlaid (thin = annual anomaly, thick = monotone axis).
    picontrol_baseline.png -- one panel per model: piControl GMSAT with the
        full-run baseline (blue band) and branch year (red dashed) marked.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # --- Figure A: ramp-up GWL overlay (0--4 degC mapping window) --------------
    figA, axA = plt.subplots(figsize=(9, 6))
    plotted = [d for d in diags if d.ru_years is not None and d.ru_anom is not None]
    t_max = 0.0
    for d in plotted:
        t = d.ru_years - d.ru_years[0]
        t, gwl_axis, gwl_anom = _trim_to_gwl_window(t, d.ru_taxis, d.ru_anom)
        if t.size == 0:
            continue
        t_max = max(t_max, float(t[-1]))
        (line,) = axA.plot(t, gwl_axis, lw=2, label=f"{d.model}")
        axA.plot(t, gwl_anom, lw=0.8, alpha=0.35, color=line.get_color())
    axA.axhline(0.0, color="k", lw=0.6, alpha=0.2)
    axA.axhline(4.0, color="k", lw=0.6, alpha=0.2)
    xs = np.array([0.0, min(t_max, GWL_PLOT_HI / 0.02)])
    axA.plot(
        xs,
        0.02 * xs,
        color="0.3",
        ls="--",
        lw=1.2,
        label="2 °C/century",
    )
    axA.set_xlabel("years since ramp-up start")
    axA.set_ylabel(r"GWL ($\degree$C)")
    axA.set_ylim(*GWL_YLIM)
    axA.legend(ncol=2, framealpha=0.0, loc="upper left", bbox_to_anchor=(0, 0.96))
    figA.tight_layout()
    pathA = outdir / "rampup_anomaly.png"
    figA.savefig(pathA, dpi=300)
    plt.close(figA)

    # --- Figure B: piControl panels -------------------------------------------
    pmodels = [d for d in diags if d.pi_years is not None]
    if pmodels:
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch

        ncol = 2
        nrow = int(np.ceil(len(pmodels) / ncol))
        figB, axes = plt.subplots(nrow, ncol, figsize=(11, 2.6 * nrow), squeeze=False)
        for ax, d in zip(axes.flat, pmodels):
            ax.plot(d.pi_years, d.pi_gmsat, color="0.55", lw=0.8)
            ref = d.pi_reference
            if np.isfinite(d.base_span_lo) and np.isfinite(d.base_span_hi):
                lo, hi = d.base_span_lo, d.base_span_hi
                ax.axvspan(lo, hi, color="C0", alpha=0.15)
                ax.hlines(ref, lo, hi, colors="C0", lw=1.2)
            else:
                ax.axhline(ref, color="C0", lw=1.0)
            if d.branch_used is not None:
                ax.axvline(d.branch_used, color="C3", ls="--", lw=1.0)
            ax.set_title(
                f"{d.model}: ref {d.pi_reference:.2f} K, "
                f"drift {d.pi_drift:+.2f}/cy [{d.baseline_method}]",
                fontsize=8,
            )
            ax.tick_params(labelsize=7)

        legend_handles = [
            Line2D([0], [0], color="0.55", lw=0.8, label="piControl GMSAT"),
            Line2D(
                [0],
                [0],
                color="C0",
                lw=1.2,
                label="baseline reference (full piControl mean)",
            ),
            Patch(facecolor="C0", alpha=0.15, label="piControl span used for baseline"),
            Line2D([0], [0], color="C3", ls="--", lw=1.0, label="branch year"),
        ]
        for ax in axes.flat[len(pmodels) :]:
            ax.set_visible(False)

        figB.suptitle("piControl GMSAT and full-run baseline")
        # reserve a strip at the bottom for a single-row legend
        figB.tight_layout(rect=[0, 0.06, 1, 1])
        figB.legend(
            handles=legend_handles,
            loc="lower center",
            ncol=5,
            # fontsize=8,
            frameon=False,
            bbox_to_anchor=(0.5, 0.0),
        )
        pathB = outdir / "picontrol_baseline.png"
        figB.savefig(pathB, dpi=300)
        plt.close(figB)
    else:
        pathB = None

    return pathA, pathB
