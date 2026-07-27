"""
Figure 2: piControl GMSAT with the full-run baseline.

Figure 1 (ramp-up / ramp-down monotone GWL axes) is produced by
``plot_mapping_axis_up_down.py`` — see ``build_all.py``.

Usage::

    python paper/figures_1_2.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(PAPER_DIR))

from run_diagnostics import print_table, run_diagnostics
from plot_diagnostics import plot_diagnostics
DEFAULT_OUT_DIR = PAPER_DIR / "figures"


def main(up2p0_dir, picontrol_dir, window=31, out_dir=None):
    diags = run_diagnostics(up2p0_dir, picontrol_dir, window=window)
    print_table(diags)
    out_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    _path_a, path_b = plot_diagnostics(diags, out_dir, rampup=False)
    if path_b:
        print(f"Saved {path_b}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build piControl baseline figure.")
    parser.add_argument("--up2p0-dir", required=True)
    parser.add_argument("--picontrol-dir", required=True)
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, window=args.window, out_dir=args.out_dir)
