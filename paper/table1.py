"""
Build Table 1 (per-model baseline and robustness diagnostics) as a CSV.

Combines what run_diagnostics already computes (branch year, drift,
monotonization_max, baseline_method) with the full-vs-window baseline
comparison (the same computation as baseline_sensitivity.py) into one
per-model table, matching the SI table in the paper draft.

Usage::

    python paper/table1.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tipmip_gwl.baseline import compute_baseline, legacy_window_reference
from tipmip_gwl.diagnostics import run_diagnostics

DEFAULT_OUT_CSV = Path(__file__).resolve().parent / "tables" / "table1.csv"


def _ref_window(d, window=31):
    """(ref_window, note) -- mirrors baseline_sensitivity.py's exclusions."""
    if d.branch_used is None:
        return None, "no branch year"
    branch = d.branch_used
    if not (d.pi_years.min() <= branch <= d.pi_years.max()):
        return None, "branch year out of range"
    try:
        return legacy_window_reference(d.pi_years, d.pi_gmsat, branch, window=window), None
    except ValueError:
        return None, "window unavailable"


def main(up2p0_dir, picontrol_dir, window=31, out_csv=None):
    diags = run_diagnostics(up2p0_dir, picontrol_dir, window=window)

    rows = []
    for d in diags:
        if d.pi_years is None:
            continue  # no piControl at all; not mappable (excluded, not in v1)
        ref_win, note = _ref_window(d, window=window)
        ref_full = compute_baseline(d.pi_years, d.pi_gmsat, d.branch_used).reference
        d_ref = abs(ref_full - ref_win) if ref_win is not None else None
        rows.append(
            {
                "model": d.model,
                "branch_year": d.branch_used,
                "baseline_method": d.baseline_method,
                "picontrol_drift_degC_per_cy": d.pi_drift,
                "ref_full_K": ref_full,
                "ref_window_K": ref_win,
                "abs_dref_K": d_ref,
                "mono_max_degC": d.monotonization_max,
                "note": note or "",
            }
        )

    hdr = (
        f"{'model':<22} {'branch':>7} {'drift':>8} {'ref_full':>9} "
        f"{'ref_win':>9} {'dref':>7} {'mono_max':>9}  note"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        by = f"{r['branch_year']:.0f}" if r["branch_year"] is not None else "-"
        rw = f"{r['ref_window_K']:.3f}" if r["ref_window_K"] is not None else "-"
        dr = f"{r['abs_dref_K']:.3f}" if r["abs_dref_K"] is not None else "not tested"
        print(
            f"{r['model']:<22} {by:>7} {r['picontrol_drift_degC_per_cy']:+8.3f} "
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
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
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
