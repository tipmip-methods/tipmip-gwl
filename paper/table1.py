"""
Build Table 1 (per-model baseline and robustness diagnostics) as a CSV.

Combines what run_diagnostics already computes (branch year, drift,
monotonization_max) with the full-vs-window baseline comparison (the same
computation as baseline_sensitivity.py) into one per-model table, matching the
SI table in the paper draft.

Usage::

    python paper/table1.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from tipmip_gwl.diagnostics import run_diagnostics

DEFAULT_OUT_CSV = Path(__file__).resolve().parent / "tables" / "table1.csv"

FIELDNAMES = (
    "model",
    "branch_year",
    "picontrol_range",
    "picontrol_drift_degC_per_cy",
    "ref_full_K",
    "ref_window_K",
    "abs_dref_K",
    "mono_max_degC",
    "note",
)


def _r3(x):
    """Round to three decimals; pass through None."""
    return None if x is None else round(float(x), 3)

def _baseline_note(d, window=31):
    """Note when the published baseline could not use a branch-window mean."""
    if d.branch_used is None:
        return "no branch year"
    branch = d.branch_used
    if not (d.pi_years.min() <= branch <= d.pi_years.max()):
        return "branch year out of range"
    return ""


def main(up2p0_dir, picontrol_dir, window=31, out_csv=None):
    diags = run_diagnostics(up2p0_dir, picontrol_dir, window=window)

    rows = []
    for d in diags:
        if d.pi_years is None:
            continue  # no piControl at all; not mappable (excluded, not in v1)
        ref_win = d.pi_reference
        ref_full = d.pi_reference_full
        note = _baseline_note(d, window=window)
        d_ref = abs(ref_full - ref_win) if np.isfinite(ref_full) and np.isfinite(ref_win) else None
        pi_range = f"{int(d.pi_years.min())}–{int(d.pi_years.max())}"
        rows.append(
            {
                "model": d.model,
                "branch_year": _r3(d.branch_used),
                "picontrol_range": pi_range,
                "picontrol_drift_degC_per_cy": _r3(d.pi_drift),
                "ref_full_K": _r3(ref_full),
                "ref_window_K": _r3(ref_win),
                "abs_dref_K": _r3(d_ref),
                "mono_max_degC": _r3(d.monotonization_max),
                "note": note or "",
            }
        )

    # Same order as Figure 3 (mean_tas_piControl.py): ascending full piControl mean.
    rows.sort(key=lambda r: r["ref_full_K"])

    hdr = (
        f"{'model':<22} {'branch':>7} {'picontrol':>11} {'drift':>8} {'ref_full':>9} "
        f"{'ref_win':>9} {'dref':>7} {'mono_max':>9}  note"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        by = (
            f"{r['branch_year']:.0f}"
            if r["branch_year"] is not None
            else "-"
        )
        rw = f"{r['ref_window_K']:.3f}" if r["ref_window_K"] is not None else "-"
        dr = f"{r['abs_dref_K']:.3f}" if r["abs_dref_K"] is not None else "not tested"
        print(
            f"{r['model']:<22} {by:>7} {r['picontrol_range']:>11} "
            f"{r['picontrol_drift_degC_per_cy']:+8.3f} "
            f"{r['ref_full_K']:9.3f} {rw:>9} {dr:>10} "
            f"{r['mono_max_degC']:9.3f}  {r['note']}"
        )

    tested = [r["abs_dref_K"] for r in rows if r["abs_dref_K"] is not None]
    if tested:
        print(f"\nmax |dref| = {max(tested):.3f} K across {len(tested)} tested models")
    print(f"mono_max <= {max(r['mono_max_degC'] for r in rows):.3f} degC for all models")

    out_csv = Path(out_csv) if out_csv else DEFAULT_OUT_CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Table 1 as a CSV.")
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, window=args.window, out_csv=args.out_csv)
