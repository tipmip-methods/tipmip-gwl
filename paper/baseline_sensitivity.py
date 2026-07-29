"""
Compare full piControl mean vs the published 31-yr branch-window baseline.

Reproduces the baseline sensitivity table: drift is small and
|full piControl mean − 31-yr branch window| is at most ~0.09 K for models with
a decodable branch year inside piControl. The published baseline is now the
window mean; this script keeps the full-vs-window comparison for robustness.

Usage::

    python paper/baseline_sensitivity.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tipmip_gwl.baseline import (
    branch_year_from_attrs,
    compute_baseline,
    discover_mappable_models,
    resolve_branch_year,
)
from tipmip_gwl.io import load_gmsat_nc, read_attrs
from tipmip_gwl.mapping import picontrol_reference

DEFAULT_OUT_CSV = Path(__file__).resolve().parent / "tables" / "baseline_sensitivity.csv"


def main(up2p0_dir, picontrol_dir, window=31, out_csv=None):
    rows = []
    for model, ru_path, pi_path in discover_mappable_models(
        up2p0_dir, picontrol_dir, bundled_only=True
    ):
        ru_years, _ = load_gmsat_nc(ru_path)
        pi_years, pi_gmsat = load_gmsat_nc(pi_path)
        bi = branch_year_from_attrs(read_attrs(ru_path))
        branch, _ = resolve_branch_year(bi, model, ru_years, pi_years)
        if branch is None:
            continue  # no branch year decoded (e.g. no parent declared): can't
            # centre a window; the full-mean baseline doesn't need it either
        if not (pi_years.min() <= branch <= pi_years.max()):
            continue
        published = compute_baseline(
            pi_years, pi_gmsat, branch, window=window,
        )
        if not published.method.startswith("branch_window"):
            continue
        win_ref = published.reference
        ref_full = picontrol_reference(pi_years, pi_gmsat, branch)
        span_yr = float(pi_years.max() - pi_years.min())
        drift = published.drift_degC_per_century
        total = drift * span_yr / 100.0
        rows.append(
            (
                model,
                drift,
                total,
                ref_full,
                win_ref,
                abs(ref_full - win_ref),
            )
        )

    hdr = (
        f"{'Model':<22} {'drift':>8} {'total':>7} {'ref_full':>8} "
        f"{'ref_win':>8} {'d_ref':>7}"
    )
    print(hdr)
    print("-" * len(hdr))
    for model, drift, total, ref_full, ref_win, d_ref in rows:
        print(
            f"{model:<22} {drift:+8.3f} {total:+7.3f} {ref_full:8.3f} "
            f"{ref_win:8.3f} {d_ref:+7.3f}"
        )

    if rows:
        max_d = max(r[-1] for r in rows)
        print(
            f"\n{len(rows)} mappable model(s); max |ref_full - ref_window| = {max_d:.3f} K"
        )

    out_csv = Path(out_csv) if out_csv else DEFAULT_OUT_CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "drift_degC_per_century", "total_drift_degC",
                          "ref_full_K", "ref_window_K", "abs_dref_K"])
        writer.writerows(rows)
    print(f"Saved {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full piControl mean vs 31-yr branch-window baseline sensitivity."
    )
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument(
        "--window",
        type=int,
        default=31,
        help="branch-window width (years)",
    )
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, window=args.window, out_csv=args.out_csv)
