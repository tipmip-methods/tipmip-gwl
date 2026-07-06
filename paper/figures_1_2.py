"""
Figures 1 and 2: ramp-up GWL overlay, and piControl GMSAT with the full-run
baseline.

Thin wrapper around tipmip_gwl.diagnostics.run_diagnostics +
tipmip_gwl.plotting.plot_diagnostics (also reachable via the installed
``tipmip-gwl-diagnostics --plot`` CLI); kept as its own paper/ script so every
figure has exactly one generating script with the same --up2p0-dir/
--picontrol-dir/--out-dir convention as the rest of the pipeline.

Usage::

    python paper/figures_1_2.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tipmip_gwl.diagnostics import print_table, run_diagnostics
from tipmip_gwl.plotting import plot_diagnostics

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "figures"


def main(up2p0_dir, picontrol_dir, window=31, out_dir=None):
    diags = run_diagnostics(up2p0_dir, picontrol_dir, window=window)
    print_table(diags)
    out_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    path_a, path_b = plot_diagnostics(diags, out_dir)
    print(f"Saved {path_a}")
    if path_b:
        print(f"Saved {path_b}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Figures 1 and 2.")
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, window=args.window, out_dir=args.out_dir)
