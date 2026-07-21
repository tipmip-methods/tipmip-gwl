"""Investigate TIPMIP ramp-down GMSAT curves (esm-up2p0-gwl2p0-50y-dn2p0).

Quick inspection script (not the published mapping pipeline). Computes anomalies
with ``compute_baseline`` using the ramp-down leg's branch metadata against
piControl — unlike :mod:`tipmip_gwl.rampdown`, which inherits the ramp-up
mapping baseline when a product is available in ``mapping_dir``.

Ramp-down legs cool monotonically in calendar time, but they must *not* be
remapped with the ramp-up ``year_of_gwl`` grid — same GWL on the way up and
down is a different Earth-system state (see ``tipmip_gwl.mapping`` scope notes).

Example::

    python examples/investigate_rampdown.py \\
        --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \\
        --plotdir figures/rampdown
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from tipmip_gwl.baseline import compute_baseline, resolve_branch_year, branch_year_from_attrs
from tipmip_gwl.io import discover, load_gmsat_nc, read_attrs
from tipmip_gwl.mapping import to_anomaly

DEFAULT_DN = Path("/Users/jakobharteg/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon")
DEFAULT_PI = Path("/Users/jakobharteg/Desktop/tipmip/tas/esm-piControl/gmstmon")


def load_rampdown_series(
    dn_dir: Path,
    pi_dir: Path,
) -> list[dict]:
    dn_files = discover(dn_dir)
    pi_files = discover(pi_dir)
    rows: list[dict] = []

    for model in sorted(dn_files):
        dn_path = dn_files[model]
        pi_path = pi_files.get(model)
        if pi_path is None:
            print(f"SKIP {model}: no piControl gmstmon")
            continue

        dn_years, dn_gmsat = load_gmsat_nc(dn_path)
        pi_years, pi_gmsat = load_gmsat_nc(pi_path)
        dn_attrs = read_attrs(dn_path)
        bi = branch_year_from_attrs(dn_attrs)
        try:
            branch, _ = resolve_branch_year(bi, model, dn_years, pi_years)
        except ValueError:
            branch = bi.year
        base = compute_baseline(pi_years, pi_gmsat, branch)
        anom = to_anomaly(dn_years, dn_gmsat, base.reference)

        cooling = np.diff(anom)
        mono_down = bool(np.all(cooling <= 1e-6)) if len(cooling) else True

        rows.append(
            {
                "model": model,
                "path": dn_path,
                "years": dn_years,
                "gmsat": dn_gmsat,
                "anom": anom,
                "baseline": base.reference,
                "year0": int(dn_years[0]),
                "year1": int(dn_years[-1]),
                "gwl_start": float(anom[0]),
                "gwl_end": float(anom[-1]),
                "gwl_min": float(np.nanmin(anom)),
                "gwl_max": float(np.nanmax(anom)),
                "monotone_cooling": mono_down,
                "experiment_id": str(dn_attrs.get("experiment_id", "")),
            }
        )
    return rows


def print_table(rows: list[dict]) -> None:
    header = (
        f"{'model':22s}  {'years':>13s}  {'GWL start':>9s}  {'GWL end':>8s}  "
        f"{'cooling?':>8s}  experiment_id"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        yr = f"{r['year0']}-{r['year1']}"
        cool = "yes" if r["monotone_cooling"] else "no"
        print(
            f"{r['model']:22s}  {yr:>13s}  {r['gwl_start']:9.3f}  "
            f"{r['gwl_end']:8.3f}  {cool:>8s}  {r['experiment_id']}"
        )


def plot_curves(rows: list[dict], plotdir: Path | None) -> None:
    if not rows:
        return

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)

    for r in rows:
        axes[0].plot(r["years"], r["anom"], lw=1.5, label=r["model"])
        axes[1].plot(r["anom"], r["anom"], lw=0)  # keep axis scaling
        axes[1].plot(r["anom"], r["years"], lw=1.5, label=r["model"])

    axes[0].axhline(2.0, color="0.5", ls="--", lw=0.8)
    axes[0].axhline(0.0, color="0.5", ls=":", lw=0.8)
    axes[0].set_xlabel("Calendar year")
    axes[0].set_ylabel("GMSAT anomaly vs piControl (K)")
    axes[0].set_title("Ramp-down leg (after 50y ZE at +2°C)")
    axes[0].legend(fontsize=7, ncol=2, loc="upper right")
    axes[0].grid(True, alpha=0.3)

    axes[1].axvline(2.0, color="0.5", ls="--", lw=0.8)
    axes[1].axvline(0.0, color="0.5", ls=":", lw=0.8)
    axes[1].set_xlabel("GMSAT anomaly (K) ≈ GWL reached")
    axes[1].set_ylabel("Calendar year")
    axes[1].set_title("Native GWL axis (not the shared ramp-up grid)")
    axes[1].grid(True, alpha=0.3)

    if plotdir is not None:
        plotdir.mkdir(parents=True, exist_ok=True)
        out = plotdir / "rampdown_gmsat_curves.png"
        fig.savefig(out, dpi=200, bbox_inches="tight")
        print(f"Wrote {out}")
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dn-dir", type=Path, default=DEFAULT_DN)
    parser.add_argument("--picontrol-dir", type=Path, default=DEFAULT_PI)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--plotdir", type=Path, default=None)
    args = parser.parse_args()

    rows = load_rampdown_series(args.dn_dir, args.picontrol_dir)
    print_table(rows)
    if args.plot or args.plotdir is not None:
        plot_curves(rows, args.plotdir)


if __name__ == "__main__":
    main()
