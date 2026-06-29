"""
Smoothing-window sensitivity: how much does 21 vs 31 vs 41 years move the
year assigned to a fixed GWL?

CSV table supporting the robustness discussion (Sect. 2.3). Not reproduced in
full in the manuscript appendix; values are summarised in prose.

Usage::

    python paper/table_window_sensitivity.py \\
        --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from tipmip_gwl.baseline import (
    branch_year_from_attrs,
    compute_baseline,
    discover_mappable_models,
    resolve_branch_year,
)
from tipmip_gwl.io import load_gmsat_nc, read_attrs
from tipmip_gwl.mapping import MappingConfig, map_model

WINDOWS = (21, 31, 41)
GWL_TARGETS = (1.0, 1.5, 2.0)
NOMINAL_RATE_DEGC_PER_YEAR = 0.02  # 2 degC/century, the protocol's nominal ramp
DEFAULT_OUT_CSV = Path(__file__).resolve().parent / "tables" / "table_window_sensitivity.csv"


def main(
    up2p0_dir, picontrol_dir, windows=WINDOWS, gwl_targets=GWL_TARGETS, out_csv=None
):
    t_grid = np.asarray(gwl_targets, float)
    spreads = {g: [] for g in gwl_targets}
    per_model_rows = []

    hdr = f"{'Model':<22}" + "".join(f"  GWL={g:>4.1f} shift(yr)" for g in gwl_targets)
    print(hdr)
    print("-" * len(hdr))

    for model, ru_path, pi_path in discover_mappable_models(
        up2p0_dir, picontrol_dir, bundled_only=True
    ):
        ru_years, ru_gmsat = load_gmsat_nc(ru_path)
        pi_years, pi_gmsat = load_gmsat_nc(pi_path)
        bi = branch_year_from_attrs(read_attrs(ru_path))
        branch, _ = resolve_branch_year(bi, model, ru_years, pi_years)
        base = compute_baseline(pi_years, pi_gmsat, branch)

        t_of_T_by_window = {}
        for w in windows:
            cfg = MappingConfig(window=w, T_grid=t_grid)
            mm = map_model(
                model,
                ru_years,
                ru_gmsat,
                pi_years,
                pi_gmsat,
                branch,
                cfg=cfg,
                pi_reference=base.reference,
            )
            t_of_T_by_window[w] = mm.t_of_T

        row = f"{model:<22}"
        row_vals = {}
        for i, g in enumerate(gwl_targets):
            vals = np.array([t_of_T_by_window[w][i] for w in windows])
            if np.all(np.isnan(vals)):
                row += f"{'nan':>18}"
                row_vals[g] = float("nan")
                continue
            spread = float(np.nanmax(vals) - np.nanmin(vals))
            spreads[g].append(spread)
            row_vals[g] = spread
            row += f"{spread:18.2f}"
        print(row)
        per_model_rows.append((model, *(row_vals[g] for g in gwl_targets)))

    print()
    summary_rows = []
    for g in gwl_targets:
        if not spreads[g]:
            continue
        max_shift = max(spreads[g])
        equiv_degc = max_shift * NOMINAL_RATE_DEGC_PER_YEAR
        print(
            f"GWL={g:.1f}: max year-shift across window={list(windows)} "
            f"= {max_shift:.2f} yr (~{equiv_degc:.3f} degC at "
            f"{NOMINAL_RATE_DEGC_PER_YEAR * 100:.0f} degC/century), "
            f"n={len(spreads[g])} models"
        )
        summary_rows.append((g, max_shift, equiv_degc, len(spreads[g])))

    out_csv = Path(out_csv) if out_csv else DEFAULT_OUT_CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", *(f"shift_yr_at_gwl_{g}" for g in gwl_targets)])
        writer.writerows(per_model_rows)
        writer.writerow([])
        writer.writerow(["gwl", "max_shift_yr", "equiv_degC", "n_models"])
        writer.writerows(summary_rows)
    print(f"Saved {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoothing-window (21/31/41 yr) sensitivity of year-at-GWL."
    )
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, out_csv=args.out_csv)
