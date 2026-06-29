"""Synthetic end-to-end demo of the mapping algorithm (no NetCDF required)."""

import numpy as np

from tipmip_gwl import MappingConfig, map_model, sensitivity_matrix


def main():
    rng = np.random.default_rng(0)

    pi_years = np.arange(1, 701)
    pi_gmsat = (
        286.5 + 0.00005 * (pi_years - 350) + 0.12 * rng.standard_normal(pi_years.size)
    )
    branch_year = 350

    ru_years = np.arange(branch_year, branch_year + 220)
    t = ru_years - branch_year
    true_anom = 0.02 * t + 0.00003 * t**2
    pi_ref_true = 286.5
    ru_gmsat = pi_ref_true + true_anom + 0.13 * rng.standard_normal(t.size)
    co2 = 285 + 4.0 * t + 8 * rng.standard_normal(t.size)

    cfg = MappingConfig(
        window=31, method="running_mean", T_grid=np.arange(0.0, 2.0001, 0.1)
    )
    mm = map_model(
        "SYNTH-ESM",
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch_year,
        extra_vars={"atmCO2": (ru_years, co2)},
        cfg=cfg,
    )

    print("=== piControl reference GMSAT ===")
    print(
        f"  recovered: {mm.diagnostics['pi_reference_GMSAT']:.4f} "
        f"(true ~{pi_ref_true:.4f})"
    )
    print("\n=== monotonicity diagnostics ===")
    for k, v in mm.diagnostics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print("\n=== year at each GWL (t of T) ===")
    for T, tt in zip(mm.T_grid, mm.t_of_T):
        yr = f"{tt:7.1f}" if np.isfinite(tt) else "    nan"
        print(f"  GWL {T:4.1f} degC -> year {yr}")

    sens = sensitivity_matrix(
        "SYNTH-ESM",
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch_year,
        target_var=ru_gmsat,
    )
    idx = int(np.argmin(np.abs(cfg.T_grid - 1.5)))
    vals_15 = np.array([v[idx] for v in sens.values()])
    print(
        f"\n  GMSAT at GWL=1.5 across {len(sens)} configs: "
        f"spread(max-min) {np.nanmax(vals_15) - np.nanmin(vals_15):.3f} K"
    )


if __name__ == "__main__":
    main()
