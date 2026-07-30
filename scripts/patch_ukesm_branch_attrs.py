#!/usr/bin/env python3
"""
Patch CMIP parent-branch global attributes onto staged UKESM NetCDF files.

UKESM TIPMIP runs were published without reliable ``branch_time_in_parent`` /
parent metadata (TerraFIRMA ``experiment_id`` / internal ``source_id``). Branch
years follow Jeremy Walton (Met Office, July 2026, ``addMetadata.py``); this
script also writes the CMIP ``parent_*`` attrs that ``tipmip_gwl`` expects.

Branch years are on the esm-up2p0 timeline (start reset to 1850), except
``esm-up2p0`` itself which branches from piControl year 2277.

Usage::

    python scripts/patch_ukesm_branch_attrs.py --dry-run
    python scripts/patch_ukesm_branch_attrs.py --apply
    python scripts/patch_ukesm_branch_attrs.py --apply --tipmip-root ~/data/tipmip
    python scripts/patch_ukesm_branch_attrs.py --apply --include-mlotst
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import netCDF4 as nc

DEFAULT_TIPMIP_ROOT = Path.home() / "data/tipmip"
MODEL = "UKESM1-2-LL"
INTERNAL_SOURCE_ID = "eUKESM1-1-ice-N96ORCA1"
PARENT_SOURCE_ID = INTERNAL_SOURCE_ID
PARENT_UNITS = "days since 1850-01-01"

# Jeremy Walton, Met Office addMetadata.py (16-07-2026).
# Keys are CMIP ``experiment_id`` values parsed from the filename.
JEREMY_BRANCH_YEAR: dict[str, int] = {
    "esm-piControl": 0,
    "esm-up2p0": 2277,  # year in parent piControl; esm-up2p0 start reset to 1850
    "esm-up2p0-gwl2p0": 1944,
    "esm-up2p0-gwl2p0-50y-dn2p0": 1994,
    "esm-up2p0-gwl4p0": 2044,
    "esm-up2p0-gwl4p0-50y-dn2p0": 2094,
    "esm-up2p0-gwl4p0-50y-dn2p0-gwl2p0": 2232,
}

PARENT_EXPERIMENT: dict[str, str] = {
    "esm-up2p0": "esm-piControl",
    "esm-up2p0-gwl2p0": "esm-up2p0",
    "esm-up2p0-gwl4p0": "esm-up2p0",
    "esm-up2p0-gwl2p0-50y-dn2p0": "esm-up2p0-gwl2p0",
    "esm-up2p0-gwl4p0-50y-dn2p0": "esm-up2p0-gwl4p0",
    "esm-up2p0-gwl4p0-50y-dn2p0-gwl2p0": "esm-up2p0-gwl4p0-50y-dn2p0",
}


def experiment_id_from_filename(path: Path) -> str | None:
    parts = path.name.split("_")
    if len(parts) < 4 or parts[2] != MODEL:
        return None
    return parts[3]


def branch_time_in_parent(branch_year: int) -> float:
    """Match Jeremy's 360-day convention: days since 1850-01-01."""
    return float((branch_year - 1850) * 360)


def attrs_for(experiment_id: str) -> dict[str, str | float] | None:
    if experiment_id not in JEREMY_BRANCH_YEAR:
        return None

    branch_year = JEREMY_BRANCH_YEAR[experiment_id]
    out: dict[str, str | float] = {
        "experiment_id": experiment_id,
        "source_id": MODEL,
    }
    if branch_year <= 0:
        return out

    parent_experiment_id = PARENT_EXPERIMENT.get(experiment_id)
    if parent_experiment_id is None:
        return None

    out.update(
        {
            "branch_method": "standard",
            "branch_time_in_parent": branch_time_in_parent(branch_year),
            "parent_time_units": PARENT_UNITS,
            "parent_source_id": PARENT_SOURCE_ID,
            "parent_experiment_id": parent_experiment_id,
            "parent_variant_label": "r1i1p1f1",
            "parent_activity_id": "CMIP",
        }
    )
    return out


def discover_files(root: Path, *, include_mlotst: bool) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*UKESM*.nc")):
        name = path.name
        if name.endswith(".bak") or "_original.nc" in name:
            continue
        if "_toad" in name or name.endswith("_anomaly.nc"):
            continue
        if not include_mlotst and not name.startswith("tas_"):
            continue
        exp = experiment_id_from_filename(path)
        if exp is None or exp not in JEREMY_BRANCH_YEAR:
            continue
        out.append(path)
    return out


def patch_file(path: Path, *, apply: bool, backup: bool) -> None:
    experiment_id = experiment_id_from_filename(path)
    if experiment_id is None:
        print(f"  skip (unrecognised name): {path}")
        return

    new_attrs = attrs_for(experiment_id)
    if new_attrs is None:
        print(f"  skip (no patch rule): {path}")
        return

    with nc.Dataset(path, "r") as ds:
        old = {
            "experiment_id": getattr(ds, "experiment_id", None),
            "source_id": getattr(ds, "source_id", None),
            "branch_time_in_parent": getattr(ds, "branch_time_in_parent", None),
            "parent_experiment_id": getattr(ds, "parent_experiment_id", None),
        }

    branch_year = JEREMY_BRANCH_YEAR[experiment_id]
    parent = PARENT_EXPERIMENT.get(experiment_id, "(none)")
    print(f"\n{path}")
    print(f"  experiment {experiment_id}; branch year {branch_year} <- {parent}")
    print(f"  was: {old}")
    if branch_year > 0:
        print(f"  new branch_time_in_parent={new_attrs['branch_time_in_parent']}")
    print(f"  new experiment_id/source_id={new_attrs['experiment_id']}/{new_attrs['source_id']}")

    if not apply:
        return

    if backup:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(path, bak)
            print(f"  backup -> {bak.name}")

    with nc.Dataset(path, "r+") as ds:
        for key, val in new_attrs.items():
            ds.setncattr(key, val)
    print("  patched")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tipmip-root", type=Path, default=DEFAULT_TIPMIP_ROOT)
    parser.add_argument("--apply", action="store_true", help="write attrs (default: dry run)")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument(
        "--include-mlotst",
        action="store_true",
        help="also patch raw mlotst annualmax files (default: tas only)",
    )
    args = parser.parse_args()

    root = args.tipmip_root.expanduser()
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== patch_ukesm_branch_attrs ({mode}) ===")
    print(f"tipmip root: {root}")

    files = discover_files(root, include_mlotst=args.include_mlotst)
    if not files:
        print("No matching UKESM files found.")
        return

    for path in files:
        patch_file(path, apply=args.apply, backup=not args.no_backup)


if __name__ == "__main__":
    main()
