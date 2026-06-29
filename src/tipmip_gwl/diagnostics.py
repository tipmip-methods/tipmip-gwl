"""
diagnostics.py
==============
The user-facing driver. It loops over a directory of ramp-up files, pairs each
with its piControl, and runs the full sanity check: provenance gate, branch-year
decode, protocol baseline (with drift), and the monotone temperature axis. The
result is a list of :class:`ModelDiag` records that :func:`print_table` and
:func:`tipmip_gwl.plotting.plot_diagnostics` consume.

This is also the command-line entry point (``tipmip-gwl-diagnostics``).

Dependencies: numpy, and the sibling :mod:`tipmip_gwl` modules.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np

from . import baseline as bl
from . import mapping
from .io import discover, load_gmsat_nc, read_attrs


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
        ok, reason = bl.provenance_check(ru_attrs)
        if not ok:
            warns.append(f"EXCLUDED (provenance): {reason}")
            diags.append(ModelDiag(
                model, None, bl.KNOWN_BRANCH_YEARS.get(model), "excluded",
                np.nan, np.nan, np.nan, False, np.nan, np.nan, "", warns,
            ))
            continue

        ru_years, ru_gmsat = load_gmsat_nc(ru_path)
        bi = bl.branch_year_from_attrs(ru_attrs)
        known = bl.KNOWN_BRANCH_YEARS.get(model)
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

        base = bl.compute_baseline(
            pi_years, pi_gmsat, branch, window=window, detrend=detrend,
            at_parent_start=bi.at_parent_start,
        )
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
        from .plotting import plot_diagnostics

        pathA, pathB = plot_diagnostics(diags, args.plotdir)
        print(f"\nwrote {pathA}")
        if pathB:
            print(f"wrote {pathB}")


if __name__ == "__main__":
    main()
