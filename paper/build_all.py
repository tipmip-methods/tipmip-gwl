"""
Build every figure and table for the paper with one command.

Rebuilds the mapping/ data product for ramp-up and ramp-down legs when data is
staged, then runs each paper/*.py script in sequence with consistent paths. Each
step is also runnable standalone (see its own docstring) -- this is purely an
orchestrator, no logic lives here.

Usage::

    python paper/build_all.py \\
        --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \\
        --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \\
        --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

from tipmip_gwl.build import write_products, write_rampdown_products

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
sys.path.insert(0, str(PAPER_DIR))

import diagnostic_remap_binned_demo  # noqa: E402
import diagnostic_remap_demo  # noqa: E402
import figures_1_2  # noqa: E402
import plot_hysteresis_mlotst  # noqa: E402
import plot_mapping_axis_up_down  # noqa: E402
import table1  # noqa: E402
import table_mono_max  # noqa: E402
import window_sensitivity  # noqa: E402
from baseline_sensitivity import main as baseline_sensitivity_main  # noqa: E402
from mean_tas_piControl import main as mean_tas_piControl_main  # noqa: E402

DEFAULT_UP2P0_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0/gmstmon"
DEFAULT_PICONTROL_DIR = Path.home() / "Desktop/tipmip/tas/esm-piControl/gmstmon"
DEFAULT_MLOTST_DIR = Path.home() / "Desktop/tipmip/mlotst/esm-up2p0"
DEFAULT_DN_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon"
DEFAULT_DN4_DIR = Path.home() / "Desktop/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon"
DEFAULT_MLOTST_DN_DIR = Path.home() / "Desktop/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0"
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


def main(up2p0_dir, picontrol_dir, mlotst_dir, mapping_dir, dn_dir=None, dn4_dir=None):
    up2p0_dir = Path(up2p0_dir)
    picontrol_dir = Path(picontrol_dir)
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)
    dn_dir = Path(dn_dir) if dn_dir else None
    dn4_dir = Path(dn4_dir) if dn4_dir else None
    have_dn = dn_dir is not None and dn_dir.exists()
    have_dn4 = dn4_dir is not None and dn4_dir.exists()

    print("=== [0/10] rebuilding mapping/ data product (ramp-up) ===")
    written, skipped = write_products(up2p0_dir, picontrol_dir, mapping_dir)
    _report_written(written, skipped)

    dn_written = []
    if have_dn:
        print("\n=== [0b/10] rebuilding mapping/ data product (ramp-down 2°C) ===")
        dn_written, dn_skipped = write_rampdown_products(dn_dir, picontrol_dir, mapping_dir)
        _report_written(dn_written, dn_skipped)
    else:
        print(f"\n=== [0b/10] ramp-down 2°C: skipped (--dn-dir not staged: {dn_dir}) ===")

    if have_dn4:
        print("\n=== [0c/10] rebuilding mapping/ data product (ramp-down 4°C) ===")
        dn4_written, dn4_skipped = write_rampdown_products(dn4_dir, picontrol_dir, mapping_dir)
        _report_written(dn4_written, dn4_skipped)
        dn_written.extend(dn4_written)
    else:
        print(f"\n=== [0c/10] ramp-down 4°C: skipped (--dn4-dir not staged: {dn4_dir}) ===")

    print("\n=== [1/10] Figure: piControl baseline ===")
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

    print("\n=== [7/10] Table A1 (SI): per-model baseline diagnostics ===")
    table1.main(up2p0_dir, picontrol_dir)

    print("\n=== [7b/10] Table A2 (SI): per-model monotonization_max by leg ===")
    table_mono_max.main(mapping_dir, up2p0_dir, picontrol_dir)

    mlotst_dn = DEFAULT_MLOTST_DN_DIR
    if dn_written:
        print("\n=== [8/10] Figure: mapping GWL axis (ramp-up and ramp-down) ===")
        out = plot_mapping_axis_up_down.main(
            mapping_dir,
            PAPER_DIR / "figures/mapping_axis_up_down.png",
        )
        print(f"  wrote {out}")

    if dn_written and mlotst_dn.exists():
        print("\n=== [9/10] Figure 5: global mlotst hysteresis (up vs ramp-down from 4 °C) ===")
        out = plot_hysteresis_mlotst.main(
            mlotst_dir,
            mlotst_dn,
            mapping_dir,
            PAPER_DIR / "figures/hysteresis_mlotst_4c.png",
        )
        print(f"  wrote {out}")
    elif not dn_written:
        print("\n=== [8–9/10] ramp-down figures: skipped (ramp-down mapping not rebuilt) ===")
    else:
        print(f"\n=== [9/10] mlotst hysteresis: skipped ({mlotst_dn} not staged) ===")

    print(f"\nAll figures/tables written under {PAPER_DIR}/figures and {PAPER_DIR}/tables")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build every paper figure and table.")
    parser.add_argument("--up2p0-dir", default=str(DEFAULT_UP2P0_DIR))
    parser.add_argument("--picontrol-dir", default=str(DEFAULT_PICONTROL_DIR))
    parser.add_argument("--mlotst-dir", default=str(DEFAULT_MLOTST_DIR))
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    parser.add_argument(
        "--dn4-dir",
        default=str(DEFAULT_DN4_DIR),
        help="ramp-down from 4°C hold gmstmon directory",
    )
    parser.add_argument(
        "--dn-dir",
        default=str(DEFAULT_DN_DIR),
        help="ramp-down from 2°C hold gmstmon directory; omit or point at a non-existent path to skip",
    )
    args = parser.parse_args()
    main(
        args.up2p0_dir,
        args.picontrol_dir,
        args.mlotst_dir,
        args.mapping_dir,
        args.dn_dir,
        args.dn4_dir,
    )
