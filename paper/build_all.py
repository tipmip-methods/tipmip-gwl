"""
Build every figure and table for the paper with one command.

Rebuilds the mapping product for ramp-up and ramp-down legs when data is
staged, then runs each paper/*.py script in sequence with consistent paths. Each
step is also runnable standalone (see its own docstring) -- this is purely an
orchestrator, no logic lives here.

Usage::

    python paper/build_all.py \\
        --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \\
        --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \\
        --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

from tipmip_gwl.build import write_products, write_rampdown_products
from tipmip_gwl.product import default_mappings_dir

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
sys.path.insert(0, str(PAPER_DIR))

import fig_remap_binned_demo  # noqa: E402
import fig_remap_demo  # noqa: E402
import fig_baseline_reference_comparison  # noqa: E402
import fig_hysteresis_mlotst  # noqa: E402
import fig_mapping_axis_up_down  # noqa: E402
import fig_picontrol_baseline  # noqa: E402
import table_baseline_sensitivity  # noqa: E402
import table_window_sensitivity  # noqa: E402
import table_baseline_diagnostics  # noqa: E402
import table_mono_max  # noqa: E402

DEFAULT_UP2P0_DIR = Path.home() / "data/tipmip/tas/esm-up2p0/gmstmon"
DEFAULT_PICONTROL_DIR = Path.home() / "data/tipmip/tas/esm-piControl/gmstmon"
DEFAULT_MLOTST_DIR = Path.home() / "data/tipmip/mlotst/esm-up2p0"
DEFAULT_DN_DIR = Path.home() / "data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon"
DEFAULT_DN4_DIR = Path.home() / "data/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon"
DEFAULT_MLOTST_DN_DIR = Path.home() / "data/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0"
DEFAULT_SIVOL_UP_DIR = Path.home() / "data/tipmip/sivol/esm-up2p0"
DEFAULT_SIVOL_DN_DIR = Path.home() / "data/tipmip/sivol/esm-up2p0-gwl4p0-50y-dn2p0"
DEFAULT_MAPPING_DIR = default_mappings_dir()


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


def main(
    up2p0_dir,
    picontrol_dir,
    mlotst_dir,
    mapping_dir,
    dn_dir=None,
    dn4_dir=None,
    sivol_up_dir=None,
    sivol_dn_dir=None,
):
    up2p0_dir = Path(up2p0_dir)
    picontrol_dir = Path(picontrol_dir)
    mlotst_dir = Path(mlotst_dir)
    mapping_dir = Path(mapping_dir)
    dn_dir = Path(dn_dir) if dn_dir else None
    dn4_dir = Path(dn4_dir) if dn4_dir else None
    have_dn = dn_dir is not None and dn_dir.exists()
    have_dn4 = dn4_dir is not None and dn4_dir.exists()

    print("=== [0/10] rebuilding mapping products (ramp-up) ===")
    print(f"  mapping output: {mapping_dir}")
    written, skipped = write_products(up2p0_dir, picontrol_dir, mapping_dir)
    _report_written(written, skipped)

    dn_written = []
    if have_dn:
        print("\n=== [0b/10] rebuilding mapping products (ramp-down 2°C) ===")
        dn_written, dn_skipped = write_rampdown_products(dn_dir, picontrol_dir, mapping_dir)
        _report_written(dn_written, dn_skipped)
    else:
        print(f"\n=== [0b/10] ramp-down 2°C: skipped (--dn-dir not staged: {dn_dir}) ===")

    if have_dn4:
        print("\n=== [0c/10] rebuilding mapping products (ramp-down 4°C) ===")
        dn4_written, dn4_skipped = write_rampdown_products(dn4_dir, picontrol_dir, mapping_dir)
        _report_written(dn4_written, dn4_skipped)
        dn_written.extend(dn4_written)
    else:
        print(f"\n=== [0c/10] ramp-down 4°C: skipped (--dn4-dir not staged: {dn4_dir}) ===")

    print("\n=== [1/10] fig_picontrol_baseline ===")
    fig_picontrol_baseline.main(up2p0_dir, picontrol_dir)

    print("\n=== [2/10] table_baseline_sensitivity ===")
    table_baseline_sensitivity.main(up2p0_dir, picontrol_dir)

    print("\n=== [3/10] table_window_sensitivity ===")
    table_window_sensitivity.main(up2p0_dir, picontrol_dir)

    print("\n=== [4/10] fig_baseline_reference_comparison ===")
    fig_baseline_reference_comparison.main(up2p0_dir, picontrol_dir)

    print("\n=== [5/10] fig_remap_demo ===")
    fig_remap_demo.main(mlotst_dir, mapping_dir, fig_remap_demo.DEFAULT_OUT)

    print("\n=== [6/10] fig_remap_binned_demo ===")
    fig_remap_binned_demo.main(
        mlotst_dir,
        mapping_dir,
        fig_remap_binned_demo.DEFAULT_OUT,
    )

    print("\n=== [7/10] table_baseline_diagnostics (Table A1) ===")
    table_baseline_diagnostics.main(up2p0_dir, picontrol_dir)

    print("\n=== [8/10] table_mono_max (Table A2) ===")
    table_mono_max.main(mapping_dir, up2p0_dir, picontrol_dir)

    mlotst_dn = DEFAULT_MLOTST_DN_DIR
    sivol_up = Path(sivol_up_dir) if sivol_up_dir else DEFAULT_SIVOL_UP_DIR
    sivol_dn = Path(sivol_dn_dir) if sivol_dn_dir else DEFAULT_SIVOL_DN_DIR
    if dn_written:
        print("\n=== [9/10] fig_mapping_axis_up_down ===")
        out = fig_mapping_axis_up_down.main(
            mapping_dir,
            fig_mapping_axis_up_down.DEFAULT_OUT,
        )
        print(f"  wrote {out}")

    if dn_written and mlotst_dn.exists() and sivol_up.exists() and sivol_dn.exists():
        print("\n=== [10/10] fig_hysteresis_mlotst ===")
        out = fig_hysteresis_mlotst.main(
            mlotst_dir,
            mlotst_dn,
            sivol_up,
            sivol_dn,
            mapping_dir,
            fig_hysteresis_mlotst.DEFAULT_OUT,
        )
        print(f"  wrote {out}")
    elif not dn_written:
        print("\n=== [9–10/10] ramp-down figures: skipped (ramp-down mapping not rebuilt) ===")
    elif not mlotst_dn.exists():
        print(f"\n=== [10/10] fig_hysteresis_mlotst: skipped ({mlotst_dn} not staged) ===")
    else:
        print(
            f"\n=== [10/10] fig_hysteresis_mlotst: skipped "
            f"(sivol not staged: {sivol_up} / {sivol_dn}) ==="
        )

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
    parser.add_argument("--sivol-up-dir", default=str(DEFAULT_SIVOL_UP_DIR))
    parser.add_argument("--sivol-dn-dir", default=str(DEFAULT_SIVOL_DN_DIR))
    args = parser.parse_args()
    main(
        args.up2p0_dir,
        args.picontrol_dir,
        args.mlotst_dir,
        args.mapping_dir,
        args.dn_dir,
        args.dn4_dir,
        args.sivol_up_dir,
        args.sivol_dn_dir,
    )
