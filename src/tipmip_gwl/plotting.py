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
        full-run baseline (blue line) marked; model name in the panel corner.
        No branch-year marker -- the full-mean baseline does not depend on it
        (see the baseline sensitivity comparison figure instead).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    plt.rcParams["axes.prop_cycle"] = plt.cycler(color=plt.cm.Dark2.colors)

    # --- Figure A: ramp-up GWL overlay (0--4 degC mapping window) --------------
    figA, axA = plt.subplots(figsize=(9, 6))
    plotted = [d for d in diags if d.ru_years is not None and d.ru_anom is not None]
    t_max = 0.0
    for d in plotted:
        t = d.ru_years - d.ru_years[0]
        # No longer trim to GWL window: plot entire time series
        gwl_axis = d.ru_taxis
        gwl_anom = d.ru_anom
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
    axA.set_xlabel("Years since ramp-up start")
    axA.set_ylabel(r"GWL ($\degree$C)")
    axA.set_ylim(*GWL_YLIM)
    axA.set_xlim(-5, 220)  # roughly where we reach 4 degC
    axA.legend(ncol=2, framealpha=0.0, loc="upper left", bbox_to_anchor=(0, 0.96))
    figA.tight_layout()
    pathA = outdir / "rampup_anomaly.png"
    figA.savefig(pathA, dpi=300)
    plt.close(figA)

    # --- Figure B: piControl panels -------------------------------------------
    pmodels = [d for d in diags if d.pi_years is not None]
    if pmodels:
        from matplotlib.ticker import MaxNLocator

        ncol = 4
        nrow = int(np.ceil(len(pmodels) / ncol))

        # --- Find global min/max for y-axis sharing
        y_mins = [np.nanmin(d.pi_gmsat) for d in pmodels]
        y_maxs = [np.nanmax(d.pi_gmsat) for d in pmodels]
        try:
            y_min, y_max = float(np.nanmin(y_mins)), float(np.nanmax(y_maxs))
        except Exception:
            y_min, y_max = None, None

        figB, axes = plt.subplots(nrow, ncol, figsize=(12, 2.10 * nrow), sharey=True)

        for ax_idx, (ax, d) in enumerate(zip(axes.flat, pmodels)):
            ax.plot(d.pi_years, d.pi_gmsat, color="k", lw=0.8)
            ax.axhline(d.pi_reference, color=plt.cm.tab10.colors[0], lw=1.2)
            y_pos = 0.94 if "IPSL" in str(d.model) else 0.06
            va = "top" if "IPSL" in str(d.model) else "bottom"
            ax.text(
                0.97,
                y_pos,
                d.model,
                transform=ax.transAxes,
                ha="right",
                va=va,
                fontsize=8,
            )

            # Plot d.pi_reference in the lower left of each model panel
            ax.text(
                0.03,
                y_pos,
                f"{d.pi_reference:.2f}$\degree$C",
                transform=ax.transAxes,
                ha="left",
                va=va,
                fontsize=8,
                color=plt.cm.tab10.colors[0],
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
            )

            ax.yaxis.set_major_locator(MaxNLocator(4))
            # ax.tick_params(labelsize=7)
            if y_min is not None and y_max is not None:
                ax.set_ylim(y_min, y_max)

            # Only bottom left plot gets y/x label
            row, col = divmod(ax_idx, ncol)
            if row == nrow - 1 and col == 0:
                ax.set_ylabel(r"GMSAT ($\degree$C)")
                ax.set_xlabel("Model year")
            else:
                ax.set_ylabel("")
                ax.set_xlabel("")

            ax.tick_params(labelbottom=True)

        for ax in axes.flat[len(pmodels) :]:
            ax.set_visible(False)

        figB.subplots_adjust(
            left=0.045, right=0.995, top=0.993, bottom=0.10, wspace=0.06, hspace=0.18
        )
        # Do NOT call figB.legend()

        pathB = outdir / "picontrol_baseline.png"
        figB.savefig(pathB, dpi=300, bbox_inches="tight")
        plt.close(figB)
    else:
        pathB = None

    return pathA, pathB
