#!/usr/bin/env python3
"""
Per-model ramp-up diagnostics from staged gmstmon (shared by paper tables/figures).

Computes baseline method, piControl drift, max GWL, monotonization, etc. Used by
``table_baseline_diagnostics.py``, ``fig_picontrol_baseline.py``, and related
paper scripts. Not part of the installed user API.

Standalone sanity table::

    python paper/helper_diagnostics.py \\
        --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

import numpy as np

from tipmip_gwl import baseline as bl
from tipmip_gwl import mapping
from tipmip_gwl.build import NotMappable, compute_rampup_leg
from tipmip_gwl.io import discover, load_gmsat_nc, read_attrs


@dataclass
class ModelDiag:
    model: str
    branch_year: int | None
    branch_known: int | None
    baseline_method: str
    pi_reference: float
    pi_reference_full: float
    pi_drift: float
    max_gwl: float
    monotonization_max: float
    parent: str
    warnings: list = field(default_factory=list)
    ru_years: np.ndarray | None = field(default=None, repr=False)
    ru_anom: np.ndarray | None = field(default=None, repr=False)
    ru_taxis: np.ndarray | None = field(default=None, repr=False)
    pi_years: np.ndarray | None = field(default=None, repr=False)
    pi_gmsat: np.ndarray | None = field(default=None, repr=False)
    branch_used: float | None = None
    base_span_lo: float = float("nan")
    base_span_hi: float = float("nan")


def run_diagnostics(up2p0_dir, picontrol_dir, window=31, detrend=False, *, bundled_only=False):
    ru_files = discover(up2p0_dir)
    pi_files = discover(picontrol_dir)
    if bundled_only:
        from tipmip_gwl.ensemble import INCLUDED_MODELS

        allowed = set(INCLUDED_MODELS)
    else:
        allowed = None
    diags = []

    for model in sorted(ru_files):
        if allowed is not None and model not in allowed:
            continue
        warns: list[str] = []
        ru_path = ru_files[model]
        pi_path = pi_files.get(model)

        ru_attrs = read_attrs(ru_path)
        warns.extend(bl.provenance_warnings(ru_attrs))

        ru_years, _ru_gmsat = load_gmsat_nc(ru_path)
        bi = bl.branch_year_from_attrs(ru_attrs)
        known = bl.KNOWN_BRANCH_YEARS.get(model)

        parent = "/".join(
            str(x)
            for x in [
                bi.parent_source_id,
                bi.parent_experiment_id,
                bi.parent_variant_label,
                bi.parent_mip_era,
            ]
            if x
        )

        if pi_path is None:
            warns.append("NO piControl tas -> cannot compute protocol baseline")
            diags.append(
                ModelDiag(
                    model,
                    bi.year,
                    known,
                    "none",
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    parent,
                    warns,
                )
            )
            continue

        try:
            leg = compute_rampup_leg(
                model, ru_path, pi_path, window=window, detrend=detrend,
            )
        except NotMappable as exc:
            warns.append(str(exc))
            diags.append(
                ModelDiag(
                    model,
                    bi.year,
                    known,
                    "none",
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    parent,
                    warns,
                )
            )
            continue

        warns.extend(leg.warns)
        pi_reference_full = mapping.picontrol_reference(
            leg.pi_years, leg.pi_gmsat, leg.branch, detrend=detrend
        )
        if (
            np.isfinite(leg.base.drift_degC_per_century)
            and abs(leg.base.drift_degC_per_century) > 0.5
        ):
            warns.append(
                f"piControl drift {leg.base.drift_degC_per_century:+.2f} "
                "degC/century exceeds 0.5 (baseline sensitive; consider --detrend-pi)"
            )

        mm = leg.mm
        diags.append(
            ModelDiag(
                model=model,
                branch_year=bi.year,
                branch_known=known,
                baseline_method=leg.base.method,
                pi_reference=leg.base.reference,
                pi_reference_full=pi_reference_full,
                pi_drift=leg.base.drift_degC_per_century,
                max_gwl=float(np.nanmax(mm.T_axis)),
                monotonization_max=mm.diagnostics["monotonization_max_degC"],
                parent=parent,
                warnings=warns,
                ru_years=leg.ru_years,
                ru_anom=mm.anom,
                ru_taxis=mm.T_axis,
                pi_years=leg.pi_years,
                pi_gmsat=leg.pi_gmsat,
                branch_used=float(leg.branch) if leg.branch is not None else None,
                base_span_lo=leg.base.span[0],
                base_span_hi=leg.base.span[1],
            )
        )

    return diags


def print_table(diags):
    hdr = (
        f"{'model':16s} {'brYr':>6s} {'baseline':16s} {'pi_ref':>9s} "
        f"{'drift':>9s} {'maxGWL':>7s} {'mono':>6s}"
    )
    print(hdr)
    print("-" * len(hdr))
    for d in diags:

        def f(x, w=9, p=3):
            return (
                f"{x:>{w}.{p}f}"
                if isinstance(x, float) and np.isfinite(x)
                else f"{'nan':>{w}s}"
            )

        by = (
            f"{int(d.branch_used)}"
            if d.branch_used is not None and np.isfinite(d.branch_used)
            else (f"{d.branch_year}" if d.branch_year is not None else "  -")
        )
        print(
            f"{d.model:16s} {by:>6s} {d.baseline_method:16s} {f(d.pi_reference)} "
            f"{f(d.pi_drift)} {f(d.max_gwl, 7, 2)} {f(d.monotonization_max, 6, 3)}"
        )
    print()
    for d in diags:
        if d.parent:
            print(f"  {d.model}: parent = {d.parent}")
        for w in d.warnings:
            print(f"  !! {d.model}: {w}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Per-model ramp-up diagnostics for staged gmstmon files."
    )
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--detrend-pi", action="store_true")
    args = parser.parse_args(argv)

    diags = run_diagnostics(
        args.up2p0_dir,
        args.picontrol_dir,
        window=args.window,
        detrend=args.detrend_pi,
    )
    print_table(diags)


if __name__ == "__main__":
    main(sys.argv[1:])
