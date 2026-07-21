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
BRANCH_WINDOW = 31


def _branch_window_pi(pi_years, pi_gmsat, branch_year, *, window: int = BRANCH_WINDOW):
    """Return (window_mean, win_lo, win_hi, note) for piControl baseline panels.

    Uses the same rules as :func:`tipmip_gwl.baseline.branch_window_reference`:
    centred ``window`` at ``branch_year``, trailing first ``window`` years when
    the centred window would start before piControl (ACCESS-ESM1-5). Returns
    ``(nan, nan, nan, note)`` when the branch year is missing or outside the
    staged piControl span (NorESM2-LM).
    """
    from .baseline import branch_window_reference

    if branch_year is None or not np.isfinite(branch_year):
        return np.nan, np.nan, np.nan, "no branch year"

    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)
    pi_lo, pi_hi = float(yrs.min()), float(yrs.max())
    branch = float(branch_year)

    if not (pi_lo <= branch <= pi_hi):
        return np.nan, np.nan, np.nan, "branch year out of range"

    half = window // 2
    lo, hi = branch - half, branch + half
    trailing = lo < pi_lo
    if trailing:
        win_lo, win_hi = pi_lo, pi_lo + window - 1
    else:
        win_lo, win_hi = lo, hi

    try:
        ref = branch_window_reference(yrs, vals, branch, window=window)
    except ValueError:
        return np.nan, np.nan, np.nan, "31-yr window unavailable"

    note = "trailing 31-yr" if trailing else None
    return ref, win_lo, win_hi, note


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
        published 31-yr branch-window baseline (solid), full-run mean (dashed),
        branch year (vertical line), and shaded reference window; NorESM2-LM
        omits the window when the branch year lies outside staged piControl.
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
        from matplotlib.lines import Line2D
        from matplotlib.ticker import MaxNLocator

        full_color = plt.cm.tab10.colors[0]
        window_color = plt.cm.tab10.colors[1]

        ncol = 4
        nrow = int(np.ceil(len(pmodels) / ncol))

        # --- Find global min/max for y-axis sharing
        y_mins = [np.nanmin(d.pi_gmsat) for d in pmodels]
        y_maxs = [np.nanmax(d.pi_gmsat) for d in pmodels]
        try:
            y_min, y_max = float(np.nanmin(y_mins)), float(np.nanmax(y_maxs))
        except Exception:
            y_min, y_max = None, None

        figB, axes = plt.subplots(nrow, ncol, figsize=(12, 2.35 * nrow), sharey=True)

        for ax_idx, (ax, d) in enumerate(zip(axes.flat, pmodels)):
            ax.plot(d.pi_years, d.pi_gmsat, color="k", lw=0.8)

            win_ref, win_lo, win_hi, win_note = _branch_window_pi(
                d.pi_years, d.pi_gmsat, d.branch_used
            )
            published_ref = d.pi_reference
            full_ref = d.pi_reference_full
            uses_window = d.baseline_method.startswith("branch_window")

            if np.isfinite(win_lo) and np.isfinite(win_hi):
                ax.axvspan(win_lo, win_hi, color=window_color, alpha=0.12, lw=0)
            if uses_window and np.isfinite(published_ref):
                ax.axhline(published_ref, color=window_color, lw=1.4)
            if d.branch_used is not None and np.isfinite(d.branch_used):
                ax.axvline(
                    d.branch_used,
                    color="0.35",
                    ls=":",
                    lw=0.9,
                )

            ax.axhline(full_ref, color=full_color, lw=1.0, ls="--", alpha=0.85)

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

            if uses_window and np.isfinite(published_ref):
                if d.baseline_method == "branch_window_31yr_trailing":
                    label = f"{published_ref:.2f} K (trailing 31-yr)"
                else:
                    label = f"{published_ref:.2f} K (31-yr)"
                ax.text(
                    0.03,
                    y_pos,
                    label,
                    transform=ax.transAxes,
                    ha="left",
                    va=va,
                    fontsize=7.5,
                    color=window_color,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
                )
                ax.text(
                    0.03,
                    y_pos + (0.10 if va == "bottom" else -0.10),
                    f"{full_ref:.2f} K (full mean)",
                    transform=ax.transAxes,
                    ha="left",
                    va=va,
                    fontsize=7,
                    color=full_color,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
                )
            elif win_note:
                ax.text(
                    0.03,
                    y_pos,
                    win_note,
                    transform=ax.transAxes,
                    ha="left",
                    va=va,
                    fontsize=7.5,
                    color=window_color,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
                )
                ax.text(
                    0.03,
                    y_pos + (0.10 if va == "bottom" else -0.10),
                    f"{full_ref:.2f} K (full mean)",
                    transform=ax.transAxes,
                    ha="left",
                    va=va,
                    fontsize=7,
                    color=full_color,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
                )

            if d.branch_used is not None and np.isfinite(d.branch_used):
                ax.text(
                    0.97,
                    y_pos + (0.10 if va == "bottom" else -0.10),
                    f"branch {int(d.branch_used)}",
                    transform=ax.transAxes,
                    ha="right",
                    va=va,
                    fontsize=7,
                    color="0.35",
                )

            ax.yaxis.set_major_locator(MaxNLocator(4))
            if y_min is not None and y_max is not None:
                ax.set_ylim(y_min, y_max)

            row, col = divmod(ax_idx, ncol)
            if row == nrow - 1 and col == 0:
                ax.set_ylabel(r"GMSAT (K)")
                ax.set_xlabel("Model year")
            else:
                ax.set_ylabel("")
                ax.set_xlabel("")

            ax.tick_params(labelbottom=True)

        for ax in axes.flat[len(pmodels) :]:
            ax.set_visible(False)

        figB.subplots_adjust(
            left=0.045, right=0.995, top=0.993, bottom=0.14, wspace=0.06, hspace=0.18
        )
        figB.legend(
            handles=[
                Line2D(
                    [0], [0], color=window_color, lw=1.4, label="31-yr branch window"
                ),
                Line2D(
                    [0],
                    [0],
                    color=full_color,
                    lw=1.0,
                    ls="--",
                    label="Full piControl mean",
                ),
                Line2D([0], [0], color="0.35", ls=":", lw=0.9, label="Branch year"),
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, 0.05),
            ncol=3,
            frameon=False,
            columnspacing=1.2,
            handlelength=1.8,
        )

        pathB = outdir / "picontrol_baseline.png"
        figB.savefig(pathB, dpi=300, bbox_inches="tight")
        plt.close(figB)
    else:
        pathB = None

    return pathA, pathB
