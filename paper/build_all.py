"""
Build every figure and table for the paper with one command.

Rebuilds the mapping/ data product, then runs each paper/*.py script in
sequence with consistent paths. Each step is also runnable standalone (see its
own docstring) -- this is purely an orchestrator, no logic lives here.

Usage::

    python paper/build_all.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \\
        --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0

Defaults match this machine's staged data layout; override for another.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tipmip_gwl.product import write_products

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
sys.path.insert(0, str(PAPER_DIR))  # so the sibling imports below resolve

import diagnostic_remap_demo  # noqa: E402
import figures_1_2  # noqa: E402
import table1  # noqa: E402
import window_sensitivity  # noqa: E402
from baseline_sensitivity import main as baseline_sensitivity_main  # noqa: E402
from mean_tas_piControl import main as mean_tas_piControl_main  # noqa: E402

DEFAULT_UP2P0_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0/gmstmon"
DEFAULT_PICONTROL_DIR = Path.home() / "Desktop/tipmip/tas/esm-piControl/gmstmon"
DEFAULT_MLOTST_DIR = Path.home() / "Desktop/tipmip/mlotst/esm-up2p0"
DEFAULT_MAPPING_DIR = REPO_ROOT / "mapping"


def main(up2p0_dir, picontrol_dir, mlotst_dir, mapping_dir):
    up2p0_dir = Path(up2p0_dir)
    picontrol_dir = Path(picontrol_dir)
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)

    print("=== [0/6] rebuilding mapping/ data product ===")
    written, skipped = write_products(up2p0_dir, picontrol_dir, mapping_dir)
    for model, path in written:
        print(f"  wrote {model:16s} -> {path}")
    for model, reason in skipped:
        print(f"  skip  {model:16s} -- {reason}")

    print("\n=== [1/6] Figures 1 & 2 (rampup_anomaly, picontrol_baseline) ===")
    figures_1_2.main(up2p0_dir, picontrol_dir)

    print("\n=== [2/6] Table: baseline_sensitivity (full vs 31-yr window) ===")
    baseline_sensitivity_main(up2p0_dir, picontrol_dir)

    print("\n=== [3/6] Table: window_sensitivity (21/31/41 yr smoothing) ===")
    window_sensitivity.main(up2p0_dir, picontrol_dir)

    print("\n=== [4/6] Figure 3: baseline_reference_comparison ===")
    mean_tas_piControl_main(up2p0_dir, picontrol_dir)

    print("\n=== [5/6] Figure 4: diagnostic_remap_demo ===")
    diagnostic_remap_demo.main(mlotst_dir, mapping_dir, diagnostic_remap_demo.DEFAULT_OUT)

    print("\n=== [6/6] Table 1 (SI): per-model baseline + robustness diagnostics ===")
    table1.main(up2p0_dir, picontrol_dir)

    print(f"\nAll figures/tables written under {PAPER_DIR}/figures and {PAPER_DIR}/tables")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build every paper figure and table.")
    parser.add_argument("--up2p0-dir", default=str(DEFAULT_UP2P0_DIR))
    parser.add_argument("--picontrol-dir", default=str(DEFAULT_PICONTROL_DIR))
    parser.add_argument("--mlotst-dir", default=str(DEFAULT_MLOTST_DIR))
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    args = parser.parse_args()
    main(args.up2p0_dir, args.picontrol_dir, args.mlotst_dir, args.mapping_dir)
