#!/usr/bin/env python3
"""
Patch CMIP parent-branch global attributes onto staged UKESM gmstmon files.

UKESM TIPMIP runs were published without ``branch_time_in_parent`` / parent
metadata. Branch dates were supplied separately (Met Office suite lineage,
July 2025). This script writes the standard CMIP attrs so
``tipmip_gwl.baseline.branch_year_from_attrs`` can decode them.

Branch dates are relative to the esm-up2p0 timeline (start reset to 1850),
except the ramp-up -> piControl link, which is year 2277 of piControl.

Usage::

    python scripts/patch_ukesm_branch_attrs.py --dry-run
    python scripts/patch_ukesm_branch_attrs.py --apply
    python scripts/patch_ukesm_branch_attrs.py --apply --tipmip-root ~/Desktop/tipmip/tas
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

import cftime
import netCDF4 as nc

DEFAULT_TIPMIP_ROOT = Path.home() / "Desktop/tipmip/tas"
MODEL = "UKESM1-2-LL"
SOURCE_ID = "eUKESM1-1-ice-N96ORCA1"
CALENDAR = "360_day"
PARENT_UNITS = "days since 1850-01-01"


@dataclass(frozen=True)
class BranchPatch:
    rel_path: str
    branch_year: int
    parent_experiment_id: str
    parent_source_id: str = SOURCE_ID


# Met Office branch table (suite cx209 / cy838 / …), July 2025.
PATCHES: tuple[BranchPatch, ...] = (
    BranchPatch(
        "esm-up2p0/gmstmon/tas_Amon_UKESM1-2-LL_esm-up2p0_r1i1p1f1_gn_gmstmon.nc",
        branch_year=2277,
        parent_experiment_id="esm-piControl",
    ),
    BranchPatch(
        "esm-up2p0-gwl2p0/gmstmon/tas_Amon_UKESM1-2-LL_esm-up2p0-gwl2p0_r1i1p1f1_gn_gmstmon.nc",
        branch_year=1944,
        parent_experiment_id="esm-up2p0",
    ),
    BranchPatch(
        "esm-up2p0-gwl4p0/gmstmon/tas_Amon_UKESM1-2-LL_esm-up2p0-gwl4p0_r1i1p1f1_gn_gmstmon.nc",
        branch_year=2044,
        parent_experiment_id="esm-up2p0",
    ),
    BranchPatch(
        "esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/"
        "tas_Amon_UKESM1-2-LL_esm-up2p0-gwl2p0-50y-dn2p0_r1i1p1f1_gn_gmstmon.nc",
        branch_year=1994,
        parent_experiment_id="esm-up2p0-gwl2p0",
    ),
)


def branch_time_in_parent(branch_year: int) -> float:
    date = cftime.datetime(branch_year, 1, 1, calendar=CALENDAR)
    return float(cftime.date2num(date, units=PARENT_UNITS, calendar=CALENDAR))


def attrs_for(patch: BranchPatch) -> dict[str, str | float]:
    return {
        "branch_method": "standard",
        "branch_time_in_parent": branch_time_in_parent(patch.branch_year),
        "parent_time_units": PARENT_UNITS,
        "parent_source_id": patch.parent_source_id,
        "parent_experiment_id": patch.parent_experiment_id,
        "parent_variant_label": "r1i1p1f1",
        "parent_activity_id": "CMIP",
    }


def patch_file(path: Path, patch: BranchPatch, *, apply: bool, backup: bool) -> None:
    new_attrs = attrs_for(patch)
    if not path.exists():
        print(f"  skip (missing): {path}")
        return

    with nc.Dataset(path, "r") as ds:
        old = {
            "branch_method": getattr(ds, "branch_method", None),
            "branch_time_in_parent": getattr(ds, "branch_time_in_parent", None),
            "parent_experiment_id": getattr(ds, "parent_experiment_id", None),
        }

    print(f"\n{path.relative_to(path.parents[3]) if len(path.parents) > 3 else path.name}")
    print(f"  branch year {patch.branch_year} <- {patch.parent_experiment_id}")
    print(f"  was: {old}")
    print(f"  new branch_time_in_parent={new_attrs['branch_time_in_parent']}")

    if not apply:
        return

    if backup:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(path, bak)
            print(f"  backup -> {bak.name}")

    with nc.Dataset(path, "r+") as ds:
        for key, val in new_attrs.items():
            if key in ds.ncattrs():
                ds.setncattr(key, val)
            else:
                ds.setncattr(key, val)
    print("  patched")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tipmip-root", type=Path, default=DEFAULT_TIPMIP_ROOT)
    parser.add_argument("--apply", action="store_true", help="write attrs (default: dry run)")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    root = args.tipmip_root.expanduser()
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== patch_ukesm_branch_attrs ({mode}) ===")
    print(f"tipmip root: {root}")

    for patch in PATCHES:
        patch_file(
            root / patch.rel_path,
            patch,
            apply=args.apply,
            backup=not args.no_backup,
        )


if __name__ == "__main__":
    main()
