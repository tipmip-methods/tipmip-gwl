#!/usr/bin/env python3
"""
Patch NorESM2-LM parent-branch metadata on staged NetCDF files.

Published CMIP attrs decode ``branch_time_in_parent`` to calendar year **1600**,
but NorESM confirm the ramp-up branches from piControl at **1851** (the first
piControl year). Without this patch, ``tipmip_gwl`` falls back to the full
piControl mean instead of the trailing 31-yr branch-window baseline.

Usage::

    python scripts/fix_noresm_branch_attrs.py
    python scripts/fix_noresm_branch_attrs.py --apply
    python scripts/fix_noresm_branch_attrs.py --apply --tipmip-root ~/data/tipmip
    python scripts/fix_noresm_branch_attrs.py --apply --include-mlotst
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cftime
import netCDF4 as nc
import xarray as xr

DEFAULT_TIPMIP_ROOT = Path.home() / "data/tipmip"
MODEL = "NorESM2-LM"
CANONICAL_BRANCH_YEAR = 1851  # first piControl year (NorESM, Aug 2026)
DEFAULT_PARENT_UNITS = "days since 0001-01-01"
DEFAULT_CALENDAR = "noleap"


def experiment_id_from_filename(path: Path) -> str | None:
    parts = path.name.split("_")
    if len(parts) < 4 or parts[2] != MODEL:
        return None
    return parts[3]


def _calendar_from_file(path: Path) -> str:
    try:
        with xr.open_dataset(path, decode_times=False) as ds:
            if "time" in ds.coords:
                return str(ds.time.encoding.get("calendar") or ds.time.attrs.get("calendar") or DEFAULT_CALENDAR)
    except Exception:
        pass
    return DEFAULT_CALENDAR


def branch_time_in_parent(
    branch_year: int, parent_units: str, *, calendar: str = DEFAULT_CALENDAR
) -> float:
    date = cftime.datetime(branch_year, 1, 1, calendar=calendar)
    return float(cftime.date2num(date, units=parent_units, calendar=calendar))


def decoded_branch_year(
    branch_time: float, parent_units: str, *, calendar: str = DEFAULT_CALENDAR
) -> int:
    date = cftime.num2date(branch_time, units=parent_units, calendar=calendar)
    return int(date.year)


def attrs_for(experiment_id: str, *, calendar: str) -> dict[str, str | float] | None:
    if experiment_id != "esm-up2p0":
        return None

    parent_units = DEFAULT_PARENT_UNITS
    return {
        "branch_method": "standard",
        "branch_time_in_parent": branch_time_in_parent(
            CANONICAL_BRANCH_YEAR, parent_units, calendar=calendar
        ),
        "parent_time_units": parent_units,
        "parent_source_id": MODEL,
        "parent_experiment_id": "esm-piControl",
        "parent_variant_label": "r1i1p1f1",
        "parent_activity_id": "CMIP",
    }


def discover_files(root: Path, *, include_mlotst: bool) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob(f"*{MODEL}*.nc")):
        name = path.name
        if name.endswith(".bak") or "_original.nc" in name:
            continue
        if name.endswith("_anomaly.nc"):
            continue
        if not include_mlotst and not name.startswith("tas_") and "gmstmon" not in name:
            continue
        exp = experiment_id_from_filename(path)
        if exp != "esm-up2p0":
            continue
        out.append(path)
    return out


def patch_file(path: Path, *, apply: bool, backup: bool) -> bool:
    experiment_id = experiment_id_from_filename(path)
    if experiment_id is None:
        return False

    calendar = _calendar_from_file(path)
    new_attrs = attrs_for(experiment_id, calendar=calendar)
    if new_attrs is None:
        return False

    with nc.Dataset(path, "r") as ds:
        old_bt = getattr(ds, "branch_time_in_parent", None)
        old_units = getattr(ds, "parent_time_units", None) or DEFAULT_PARENT_UNITS
        old_year = (
            decoded_branch_year(float(old_bt), str(old_units), calendar=calendar)
            if old_bt is not None
            else None
        )

    if old_year == CANONICAL_BRANCH_YEAR:
        return False

    print(f"\n{path}")
    print(f"  experiment {experiment_id}; branch year {old_year!r} -> {CANONICAL_BRANCH_YEAR}")
    print(f"  parent_time_units={new_attrs['parent_time_units']!r} calendar={calendar!r}")
    print(f"  new branch_time_in_parent={new_attrs['branch_time_in_parent']}")

    if not apply:
        return True

    if backup:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(path, bak)
            print(f"  backup -> {bak.name}")

    with nc.Dataset(path, "r+") as ds:
        for key, val in new_attrs.items():
            ds.setncattr(key, val)
    print("  patched")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tipmip-root", type=Path, default=DEFAULT_TIPMIP_ROOT)
    parser.add_argument(
        "--apply", action="store_true", help="write attrs (default: dry run)"
    )
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument(
        "--include-mlotst",
        action="store_true",
        help="also patch raw mlotst files (default: tas/gmstmon only)",
    )
    args = parser.parse_args()

    root = args.tipmip_root.expanduser()
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== fix_noresm_branch_attrs ({mode}) ===")
    print(f"tipmip root: {root}")

    files = discover_files(root, include_mlotst=args.include_mlotst)
    if not files:
        print("No matching NorESM2-LM esm-up2p0 files found.")
        return

    n_patch = sum(
        1 for path in files if patch_file(path, apply=args.apply, backup=not args.no_backup)
    )
    print(f"\nSummary: {n_patch} file(s) to patch.")
    if not args.apply:
        print("Re-run with --apply to write changes.")
        print(
            "Then rebuild gmstmon (if tas patched), NorESM gwlmap_* products, "
            "and paper figures (python paper/build_all.py)."
        )


if __name__ == "__main__":
    main()
