"""
Build every figure and table for the paper with one command.

Rebuilds the mapping/ data product for every leg that has data staged, then
runs each paper/*.py script in sequence with consistent paths. Each step is
also runnable standalone (see its own docstring) -- this is purely an
orchestrator, no logic lives here.

Usage::

    python paper/build_all.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \\
        --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \\
        --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \\
        --ze-dirs ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0/gmstmon \\
                  ~/Desktop/tipmip/tas/esm-up2p0-gwl4p0/gmstmon
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

from tipmip_gwl.product import write_products
from tipmip_gwl.rampdown import write_rampdown_products
from tipmip_gwl.zehold import write_ze_products

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
sys.path.insert(0, str(PAPER_DIR))

import diagnostic_remap_binned_demo  # noqa: E402
import diagnostic_remap_demo  # noqa: E402
import figures_1_2  # noqa: E402
import plot_up_down_trajectory  # noqa: E402
import table1  # noqa: E402
import window_sensitivity  # noqa: E402
from baseline_sensitivity import main as baseline_sensitivity_main  # noqa: E402
from mean_tas_piControl import main as mean_tas_piControl_main  # noqa: E402

DEFAULT_UP2P0_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0/gmstmon"
DEFAULT_PICONTROL_DIR = Path.home() / "Desktop/tipmip/tas/esm-piControl/gmstmon"
DEFAULT_MLOTST_DIR = Path.home() / "Desktop/tipmip/mlotst/esm-up2p0"
DEFAULT_DN_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon"
DEFAULT_ZE_DIRS = [
    Path.home() / "Desktop/tipmip/tas/esm-up2p0-gwl2p0/gmstmon",
    Path.home() / "Desktop/tipmip/tas/esm-up2p0-gwl4p0/gmstmon",
]
DEFAULT_MAPPING_DIR = REPO_ROOT / "mapping"


def _report_written(written, skipped):
    for model, path in written:
        print(f"  wrote {model:20s} -> {path.name}")
        with xr.open_dataset(path) as ds:
            warn = ds.attrs.get("mapping_warnings")
        if warn:
            for w in warn.split("; "):
                print(f"    !! {w}")
    for model, reason in skipped:
        print(f"  skip  {model:20s} -- {reason}")


def main(up2p0_dir, picontrol_dir, mlotst_dir, mapping_dir, dn_dir=None, ze_dirs=None):
    up2p0_dir = Path(up2p0_dir)
    picontrol_dir = Path(picontrol_dir)
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)
    dn_dir = Path(dn_dir) if dn_dir else None
    have_dn = dn_dir is not None and dn_dir.exists()
    ze_dirs = [Path(d) for d in (ze_dirs or [])]

    print("=== [0/10] rebuilding mapping/ data product (ramp-up) ===")
    written, skipped = write_products(up2p0_dir, picontrol_dir, mapping_dir)
    _report_written(written, skipped)

    if have_dn:
        print("\n=== [0b/10] rebuilding mapping/ data product (ramp-down) ===")
        dn_written, dn_skipped = write_rampdown_products(dn_dir, picontrol_dir, mapping_dir)
        _report_written(dn_written, dn_skipped)
    else:
        dn_written = []
        print(f"\n=== [0b/10] ramp-down: skipped (--dn-dir not staged: {dn_dir}) ===")

    ze_written_total = []
    staged_ze_dirs = [d for d in ze_dirs if d.exists()]
    if staged_ze_dirs:
        for ze_dir in staged_ze_dirs:
            print(
                f"\n=== [0c/10] rebuilding mapping/ data product "
                f"(ZE-hold: {ze_dir.parent.name}) ==="
            )
            ze_written, ze_skipped = write_ze_products(ze_dir, picontrol_dir, mapping_dir)
            _report_written(ze_written, ze_skipped)
            ze_written_total.extend(ze_written)
    else:
        print(f"\n=== [0c/10] ZE-hold: skipped (none of --ze-dirs staged: {ze_dirs}) ===")

    print("\n=== [1/10] Figures 1 & 2 (rampup_anomaly, picontrol_baseline) ===")
    figures_1_2.main(up2p0_dir, picontrol_dir)

    print("\n=== [2/10] Table: baseline_sensitivity (full vs 31-yr window) ===")
    baseline_sensitivity_main(up2p0_dir, picontrol_dir)

    print("\n=== [3/10] Table: window_sensitivity (21/31/41 yr smoothing) ===")
    window_sensitivity.main(up2p0_dir, picontrol_dir)

    print("\n=== [4/10] Figure 3: baseline_reference_comparison ===")
    mean_tas_piControl_main(up2p0_dir, picontrol_dir)

    print("\n=== [5/10] Figure 4: diagnostic_remap_demo ===")
    diagnostic_remap_demo.main(mlotst_dir, mapping_dir, diagnostic_remap_demo.DEFAULT_OUT)

    print("\n=== [6/10] Figure 4 (detail): diagnostic_remap_binned_demo ===")
    diagnostic_remap_binned_demo.main(
        mlotst_dir,
        mapping_dir,
        diagnostic_remap_binned_demo.DEFAULT_OUT,
    )

    print("\n=== [7/10] Table 1 (SI): per-model baseline + robustness diagnostics ===")
    table1.main(up2p0_dir, picontrol_dir)

    if dn_written or ze_written_total:
        print("\n=== [8/10] Preview: combined ramp-up + ZE-hold + ramp-down trajectory ===")
        out = plot_up_down_trajectory.main(
            mapping_dir, PAPER_DIR / "figures/up_down_trajectory_preview.png"
        )
        print(f"  wrote {out}")
    else:
        print("\n=== [8/10] combined trajectory preview: skipped (only ramp-up mapping) ===")

    print(f"\nAll figures/tables written under {PAPER_DIR}/figures and {PAPER_DIR}/tables")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build every paper figure and table.")
    parser.add_argument("--up2p0-dir", default=str(DEFAULT_UP2P0_DIR))
    parser.add_argument("--picontrol-dir", default=str(DEFAULT_PICONTROL_DIR))
    parser.add_argument("--mlotst-dir", default=str(DEFAULT_MLOTST_DIR))
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    parser.add_argument(
        "--dn-dir",
        default=str(DEFAULT_DN_DIR),
        help="ramp-down tas directory; omit or point at a non-existent path to skip the leg",
    )
    parser.add_argument(
        "--ze-dirs",
        nargs="*",
        default=[str(d) for d in DEFAULT_ZE_DIRS],
        help="one or more ZE-hold tas directories (space-separated); "
        "non-existent paths are skipped individually",
    )
    args = parser.parse_args()
    main(
        args.up2p0_dir,
        args.picontrol_dir,
        args.mlotst_dir,
        args.mapping_dir,
        args.dn_dir,
        args.ze_dirs,
    )
