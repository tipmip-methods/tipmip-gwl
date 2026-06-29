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


def plot_diagnostics(diags, outdir, gwl_warn=3.0):
    """Two diagnostic figures written to ``outdir``:

    rampup_anomaly.png   -- ramp-up GMSAT anomaly vs years-since-branch, all
        models overlaid (thin = annual anomaly, thick = monotone axis), with a
        2 degC/century guide. Models whose axis shoots far past the others stand
        out.
    picontrol_baseline.png -- one panel per model: piControl GMSAT with the
        branch year (red dashed) and the baseline window (blue band) marked, so
        a branch that falls outside the control span is immediately visible.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # --- Figure A: ramp-up anomaly overlay ------------------------------------
    figA, axA = plt.subplots(figsize=(9, 6))
    plotted = [d for d in diags if d.ru_years is not None and d.ru_anom is not None]
    t_max = 0.0
    for d in plotted:
        t = d.ru_years - d.ru_years[0]
        t_max = max(t_max, float(t[-1]))
        flag = " (!)" if (np.isfinite(d.max_gwl) and d.max_gwl > gwl_warn) else ""
        (line,) = axA.plot(t, d.ru_taxis, lw=2, label=f"{d.model}: max {d.max_gwl:.1f}{flag}")
        axA.plot(t, d.ru_anom, lw=0.8, alpha=0.35, color=line.get_color())
    axA.axhline(0.0, color="k", lw=0.6)
    # nominal TIPMIP ramp rate: 2 degC per century = 0.02 degC/yr from t=0
    xs = np.array([0.0, t_max])
    axA.plot(
        xs, 0.02 * xs, color="0.3", ls="--", lw=1.2,
        label="2 degC/century (nominal ramp)",
    )
    axA.set_xlabel("years since ramp-up start")
    axA.set_ylabel("GMSAT anomaly (degC)")
    axA.set_title("Ramp-up GMSAT anomaly  (thin = annual, thick = monotone axis)")
    axA.legend(fontsize=7, ncol=2)
    figA.tight_layout()
    pathA = outdir / "rampup_anomaly.png"
    figA.savefig(pathA, dpi=130)
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
            xmin, xmax = float(d.pi_years.min()), float(d.pi_years.max())
            ref = d.pi_reference
            if np.isfinite(d.base_span_lo) and np.isfinite(d.base_span_hi):
                lo, hi = d.base_span_lo, d.base_span_hi
                ax.axvspan(lo, hi, color="C0", alpha=0.15)
                ax.hlines(ref, lo, hi, colors="C0", lw=1.2)
                if lo > xmin:
                    ax.hlines(ref, xmin, lo, colors="C0", lw=0.6, ls=":", alpha=0.65)
                if hi < xmax:
                    ax.hlines(ref, hi, xmax, colors="C0", lw=0.6, ls=":", alpha=0.65)
            else:
                ax.axhline(ref, color="C0", lw=1.0)
            if d.branch_used is not None:
                ax.axvline(d.branch_used, color="C3", ls="--", lw=1.0)
            ax.set_title(
                f"{d.model}: ref {d.pi_reference:.2f} K, "
                f"drift {d.pi_drift_full:+.2f}/cy [{d.baseline_method}]",
                fontsize=8,
            )
            ax.tick_params(labelsize=7)

        legend_handles = [
            Line2D([0], [0], color="0.55", lw=0.8, label="piControl GMSAT"),
            Line2D([0], [0], color="C0", lw=1.2, label="baseline reference (mean over window)"),
            Line2D([0], [0], color="C0", lw=0.6, ls=":", alpha=0.65, label="reference level (outside window)"),
            Patch(facecolor="C0", alpha=0.15, label="baseline window"),
            Line2D([0], [0], color="C3", ls="--", lw=1.0, label="branch year"),
        ]
        for ax in axes.flat[len(pmodels):]:
            ax.set_visible(False)

        figB.suptitle("piControl GMSAT and protocol baseline window")
        # reserve a strip at the bottom for a single-row legend
        figB.tight_layout(rect=[0, 0.06, 1, 1])
        figB.legend(handles=legend_handles, loc="lower center", ncol=5,
                    fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.0))
        pathB = outdir / "picontrol_baseline.png"
        figB.savefig(pathB, dpi=130)
        plt.close(figB)
    else:
        pathB = None

    return pathA, pathB
