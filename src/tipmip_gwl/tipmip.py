"""
tipmip.py
=========
TIPMIP-specific glue around :mod:`tipmip_gwl.mapping`. Where ``mapping`` is the
pure (numpy/scipy) re-indexing algorithm, this module knows about the actual
NetCDF files and CMIP metadata, so the per-model loop can be driven straight off
the headers rather than hand-typed tables.

It provides:

* :func:`load_gmsat_nc` -- read a global-mean ``tas`` NetCDF (monthly OR annual)
  and return a calendar-aware, **days-in-month weighted** annual GMSAT series.
  This is the protocol-correct annual mean; do NOT rely on ``cdo yearmean``
  (unweighted) or even ``yearmonmean`` (equal-month) for the baseline, because a
  differential seasonal-cycle-weighting error between a model's piControl and its
  ramp-up lands directly on the zero point you match everyone against.
* :func:`provenance_check` -- reject files that are not genuine TIPMIP ramp-up
  submissions before they are mapped.
* :func:`branch_year_from_attrs` -- decode ``branch_time_in_parent`` against the
  parent calendar with ``cftime``, returning year A plus parent run identifiers.
* :func:`compute_baseline` -- protocol piControl reference with an explicit
  ``baseline_method`` flag: it falls back to a *trailing* window when the branch
  sits at/near the start of piControl (e.g. EC-Earth branches at day 0), so that
  per-model inconsistency is surfaced rather than silent.
* :func:`run_diagnostics` / :func:`plot_diagnostics` / :func:`main` -- loop the
  models, pairing ramp-up with piControl, print the sanity table and write the
  diagnostic figures.

Dependencies: numpy, xarray, cftime, and the sibling :mod:`tipmip_gwl.mapping`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import cftime
import numpy as np
import xarray as xr

from . import mapping

# Branch years independently decoded from headers (optional cross-check).
# A mismatch here flags a metadata/units problem, not science.
KNOWN_BRANCH_YEARS = {
    "GFDL-ESM2M": 1961,
    "GISS-E2-1-G-CC2": 2156,
    "IPSL-CM6-ESMCO2": 1850,
    "EC-Earth3-ESM-1": 1850,
}


# ---------------------------------------------------------------------------
# NetCDF loading -> calendar-aware annual GMSAT
# ---------------------------------------------------------------------------
def _pick_data_var(ds: xr.Dataset) -> str:
    if "tas" in ds.data_vars:
        return "tas"
    for name, da in ds.data_vars.items():
        if name.endswith("_bnds") or name.endswith("_bounds"):
            continue
        if "time" in da.dims:
            return name
    raise ValueError(f"No time-dependent data variable found in {list(ds.data_vars)}")


def load_gmsat_nc(path):
    """Load a global-mean ``tas`` file and return (years, annual_gmsat).

    The file is expected to be already reduced to a single spatial point
    (``cdo -fldmean``, area weighted). Input may be monthly or annual:

    * monthly -> a **days-in-month weighted** annual mean is computed using the
      file's own calendar (``time.dt.days_in_month``), which is the protocol mean.
    * annual  -> passes through unchanged (the weighting is a no-op per year).

    Returns numpy arrays sorted by year.
    """
    try:  # new xarray prefers a coder instance; fall back for older versions
        ds = xr.open_dataset(
            path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True)
        )
    except (AttributeError, TypeError):
        ds = xr.open_dataset(path, use_cftime=True)
    try:
        var = _pick_data_var(ds)
        da = ds[var]
        # collapse any singleton spatial dims left by fldmean
        for dim in list(da.dims):
            if dim != "time" and da.sizes[dim] == 1:
                da = da.isel({dim: 0}, drop=True)
        da = da.squeeze(drop=True)

        weights = ds["time"].dt.days_in_month
        num = (da * weights).groupby("time.year").sum(skipna=True)
        den = weights.groupby("time.year").sum(skipna=True)
        annual = num / den

        years = annual["year"].values.astype(float)
        vals = annual.values.astype(float)
    finally:
        ds.close()

    order = np.argsort(years)
    return years[order], vals[order]


def read_attrs(path) -> dict:
    """Global attrs plus the time-coordinate calendar (lives on the coord)."""
    ds = xr.open_dataset(path, decode_times=False)
    try:
        attrs = dict(ds.attrs)
        cal = None
        if "time" in ds.variables:
            cal = ds["time"].attrs.get("calendar")
        attrs["_time_calendar"] = cal
    finally:
        ds.close()
    return attrs


# ---------------------------------------------------------------------------
# Provenance gate
# ---------------------------------------------------------------------------
def provenance_check(attrs: dict, expect_experiment: str = "esm-up2p0"):
    """Validate that a ramp-up file is a genuine TIPMIP submission.

    Returns ``(ok, reason)``. A file failing any check is rejected before
    mapping rather than silently processed (e.g. a file staged under a model
    name that is actually a TerraFIRMA run, not TIPMIP).

    ``activity_id`` is matched case-insensitively because submissions use both
    'TIPMIP' and 'TipMIP'. ``branch_method`` is only rejected when it explicitly
    states 'no parent'; a missing value is tolerated so that an otherwise-valid
    file is not rejected on an absent attribute.
    """
    activity = str(attrs.get("activity_id", "")).strip()
    experiment = str(attrs.get("experiment_id", "")).strip()
    branch = str(attrs.get("branch_method", "")).strip().lower()

    if "tipmip" not in activity.lower():
        return False, f"activity_id={activity!r} is not TIPMIP"
    if expect_experiment and experiment != expect_experiment:
        return False, f"experiment_id={experiment!r} != {expect_experiment!r}"
    if branch == "no parent":
        return False, "branch_method='no parent' (no piControl linkage)"
    return True, ""


# ---------------------------------------------------------------------------
# Branch-point decoding
# ---------------------------------------------------------------------------
@dataclass
class BranchInfo:
    year: int | None
    parent_source_id: str | None = None
    parent_variant_label: str | None = None
    parent_experiment_id: str | None = None
    parent_activity_id: str | None = None
    parent_mip_era: str | None = None
    calendar: str | None = None
    at_parent_start: bool = False  # branch_time_in_parent == 0
    raw_branch_time: float | None = None
    note: str = ""


def branch_year_from_attrs(attrs: dict, calendar: str | None = None) -> BranchInfo:
    """Decode year A from CMIP ``branch_time_in_parent`` against the parent calendar.

    ``calendar`` defaults to the child file's time calendar (same model => same
    calendar as the parent). Decode with cftime, never days/365.25, because for
    a noleap calendar the offset is an exact multiple of 365 and 365.25 arithmetic
    walks off by up to a year.
    """
    bt = attrs.get("branch_time_in_parent")
    units = attrs.get("parent_time_units")
    cal = calendar or attrs.get("_time_calendar") or attrs.get("calendar") or "standard"

    info = BranchInfo(
        year=None,
        parent_source_id=attrs.get("parent_source_id"),
        parent_variant_label=attrs.get("parent_variant_label"),
        parent_experiment_id=attrs.get("parent_experiment_id"),
        parent_activity_id=attrs.get("parent_activity_id"),
        parent_mip_era=attrs.get("parent_mip_era"),
        calendar=cal,
        raw_branch_time=None if bt is None else float(bt),
    )

    if bt is None or units is None:
        info.note = "missing branch_time_in_parent/parent_time_units"
        return info

    try:
        date = cftime.num2date(float(bt), units=units, calendar=cal)
    except Exception as exc:  # noqa: BLE001
        info.note = f"cftime decode failed: {exc}"
        return info

    info.year = int(date.year)
    info.at_parent_start = float(bt) == 0.0
    if info.at_parent_start:
        info.note = "branch at parent start (day 0): centred window not possible"
    return info


# ---------------------------------------------------------------------------
# Protocol baseline with explicit method flag
# ---------------------------------------------------------------------------
@dataclass
class Baseline:
    reference: float
    method: str  # e.g. "centred_31yr", "trailing_31yr_day0", "leading_31yr"
    window: int
    n_years: int
    span: tuple
    drift_window_degC_per_century: float
    drift_full_degC_per_century: float
    detrended: bool


def compute_baseline(pi_years, pi_gmsat, branch_year, window=31, detrend=False) -> Baseline:
    """Protocol piControl reference with a fallback window + method flag.

    Centred 31-yr mean on year A when piControl has >= window//2 years either
    side. If the branch is at/near the start (e.g. EC-Earth, day 0) it falls back
    to a *trailing* (first-``window``) mean; near the end, a *leading* (last-
    ``window``) mean. The chosen method is returned so a downstream reader knows
    a model's zero point was computed differently from the centred ones.
    """
    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)
    half = window // 2

    lo, hi = branch_year - half, branch_year + half
    if lo < yrs.min():
        start = yrs.min()
        sel = (yrs >= start) & (yrs < start + window)
        method = f"trailing_{window}yr_day0" if branch_year <= start else f"trailing_{window}yr"
    elif hi > yrs.max():
        sel = yrs > yrs.max() - window
        method = f"leading_{window}yr"
    else:
        sel = (yrs >= lo) & (yrs <= hi)
        method = f"centred_{window}yr"

    g = vals.copy()
    if detrend:
        coef = np.polyfit(yrs, vals, 1)
        g = vals - np.polyval(coef, yrs) + np.polyval(coef, branch_year)

    sel &= np.isfinite(g)
    ref = float(np.mean(g[sel]))

    drift_win = mapping.picontrol_drift(yrs, vals, centre_year=branch_year, window=window)
    drift_full = mapping.picontrol_drift(yrs, vals)

    return Baseline(
        reference=ref,
        method=method,
        window=window,
        n_years=int(sel.sum()),
        span=(float(yrs[sel].min()), float(yrs[sel].max())) if sel.any() else (np.nan, np.nan),
        drift_window_degC_per_century=drift_win["drift_degC_per_century"],
        drift_full_degC_per_century=drift_full["drift_degC_per_century"],
        detrended=detrend,
    )


# ---------------------------------------------------------------------------
# File discovery / pairing
# ---------------------------------------------------------------------------
def _model_from_name(path: Path) -> str:
    # tas_<table>_<model>_<exp>_<member>_<grid>_<suffix>.nc
    return path.name.split("_")[2]


def discover(dir_path) -> dict:
    """Map model -> file for every *.nc in a directory."""
    out = {}
    for p in sorted(Path(dir_path).glob("*.nc")):
        out[_model_from_name(p)] = p
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
@dataclass
class ModelDiag:
    model: str
    branch_year: int | None
    branch_known: int | None
    baseline_method: str
    pi_reference: float
    pi_drift_window: float
    pi_drift_full: float
    pi_covers_branch: bool
    max_gwl: float
    monotonization_max: float
    parent: str
    warnings: list = field(default_factory=list)
    # series retained for plotting (None when not computed, e.g. no piControl)
    ru_years: np.ndarray | None = field(default=None, repr=False)
    ru_anom: np.ndarray | None = field(default=None, repr=False)
    ru_taxis: np.ndarray | None = field(default=None, repr=False)
    pi_years: np.ndarray | None = field(default=None, repr=False)
    pi_gmsat: np.ndarray | None = field(default=None, repr=False)
    branch_used: float | None = None
    base_span_lo: float = float("nan")
    base_span_hi: float = float("nan")


def run_diagnostics(up2p0_dir, picontrol_dir, window=31, detrend=False):
    ru_files = discover(up2p0_dir)
    pi_files = discover(picontrol_dir)
    diags = []

    for model in sorted(ru_files):
        warns = []
        ru_path = ru_files[model]
        pi_path = pi_files.get(model)

        ru_attrs = read_attrs(ru_path)
        ok, reason = provenance_check(ru_attrs)
        if not ok:
            warns.append(f"EXCLUDED (provenance): {reason}")
            diags.append(ModelDiag(
                model, None, KNOWN_BRANCH_YEARS.get(model), "excluded",
                np.nan, np.nan, np.nan, False, np.nan, np.nan, "", warns,
            ))
            continue

        ru_years, ru_gmsat = load_gmsat_nc(ru_path)
        bi = branch_year_from_attrs(ru_attrs)
        known = KNOWN_BRANCH_YEARS.get(model)
        if known is not None and bi.year is not None and known != bi.year:
            warns.append(f"branch-year mismatch: decoded {bi.year} vs known {known}")

        parent = "/".join(
            str(x) for x in [bi.parent_source_id, bi.parent_experiment_id,
                             bi.parent_variant_label, bi.parent_mip_era] if x
        )

        if pi_path is None:
            warns.append("NO piControl tas -> cannot compute protocol baseline")
            diags.append(ModelDiag(
                model, bi.year, known, "none", np.nan, np.nan, np.nan, False,
                np.nan, np.nan, parent, warns,
            ))
            continue

        pi_years, pi_gmsat = load_gmsat_nc(pi_path)
        branch = bi.year if bi.year is not None else known
        if branch is None:
            warns.append("no branch year (attrs+known both missing)")
            branch = int(pi_years[len(pi_years) // 2])

        half = window // 2
        covers = (pi_years.min() <= branch - half) and (pi_years.max() >= branch + half)
        if not covers:
            warns.append(
                f"piControl [{int(pi_years.min())}-{int(pi_years.max())}] does not "
                f"bracket branch {branch}+/-{half} -> fallback window used"
            )

        base = compute_baseline(pi_years, pi_gmsat, branch, window=window, detrend=detrend)
        # Verdict on FULL-RUN drift (genuine drift); the window slope is reported
        # for transparency but is dominated by short-segment variability.
        if (
            np.isfinite(base.drift_full_degC_per_century)
            and abs(base.drift_full_degC_per_century) > 0.5
        ):
            warns.append(
                f"piControl full-run drift {base.drift_full_degC_per_century:+.2f} "
                "degC/century exceeds 0.5 (baseline sensitive; consider --detrend-pi)"
            )

        # build axis just to report max GWL + monotonization (no payload yet)
        anom = mapping.to_anomaly(ru_years, ru_gmsat, base.reference)
        T_axis, T_pre = mapping.axis_variable(
            ru_years, anom, method="running_mean", window=window, return_intermediate=True
        )
        rep = mapping.monotonicity_report(anom, T_pre, T_axis)

        diags.append(ModelDiag(
            model=model,
            branch_year=bi.year,
            branch_known=known,
            baseline_method=base.method,
            pi_reference=base.reference,
            pi_drift_window=base.drift_window_degC_per_century,
            pi_drift_full=base.drift_full_degC_per_century,
            pi_covers_branch=bool(covers),
            max_gwl=float(np.nanmax(T_axis)),
            monotonization_max=rep["monotonization_max_degC"],
            parent=parent,
            warnings=warns,
            ru_years=ru_years,
            ru_anom=anom,
            ru_taxis=T_axis,
            pi_years=pi_years,
            pi_gmsat=pi_gmsat,
            branch_used=float(branch),
            base_span_lo=base.span[0],
            base_span_hi=base.span[1],
        ))

    return diags


def print_table(diags):
    hdr = (
        f"{'model':16s} {'brYr':>6s} {'baseline':16s} {'pi_ref':>9s} "
        f"{'drift_win':>9s} {'drift_all':>9s} {'cov':>3s} {'maxGWL':>7s} {'mono':>6s}"
    )
    print(hdr)
    print("-" * len(hdr))
    for d in diags:
        def f(x, w=9, p=3):
            return f"{x:>{w}.{p}f}" if isinstance(x, float) and np.isfinite(x) else f"{'nan':>{w}s}"
        by = f"{d.branch_year}" if d.branch_year is not None else "  -"
        print(
            f"{d.model:16s} {by:>6s} {d.baseline_method:16s} {f(d.pi_reference)} "
            f"{f(d.pi_drift_window)} {f(d.pi_drift_full)} {str(d.pi_covers_branch)[0]:>3s} "
            f"{f(d.max_gwl,7,2)} {f(d.monotonization_max,6,3)}"
        )
    print()
    for d in diags:
        if d.parent:
            print(f"  {d.model}: parent = {d.parent}")
        for w in d.warnings:
            print(f"  !! {d.model}: {w}")


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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="TIPMIP time->GWL baseline diagnostics for a set of "
        "global-mean tas NetCDF files."
    )
    parser.add_argument(
        "--up2p0-dir", required=True,
        help="directory of ramp-up (esm-up2p0) global-mean tas .nc files",
    )
    parser.add_argument(
        "--picontrol-dir", required=True,
        help="directory of piControl global-mean tas .nc files",
    )
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--detrend-pi", action="store_true")
    parser.add_argument("--plot", action="store_true", help="write diagnostic figures")
    parser.add_argument(
        "--plotdir", default="./figures",
        help="output dir for figures (with --plot); default ./figures",
    )
    args = parser.parse_args(argv)

    diags = run_diagnostics(
        args.up2p0_dir, args.picontrol_dir, window=args.window, detrend=args.detrend_pi
    )
    print_table(diags)

    if args.plot:
        pathA, pathB = plot_diagnostics(diags, args.plotdir)
        print(f"\nwrote {pathA}")
        if pathB:
            print(f"wrote {pathB}")


if __name__ == "__main__":
    main()
