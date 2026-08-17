#!/usr/bin/env python3
"""
Patch parent-branch CMIP metadata on staged TIPMIP NetCDF files.

Some models were published without reliable ``branch_time_in_parent`` and/or
``experiment_id`` / ``source_id``. This script applies modelling-group fixes
before ``tipmip_gwl`` mapping builds.

Supported models:

- **UKESM1-2-LL** — branch years from Met Office (Jeremy Walton, July 2026)
- **NorESM2-LM** — ramp-up branches at piControl year **1851** (not 1600)
- **CESM2** — ramp-up branches at piControl year **81**; missing CMIP attrs

Usage::

    python scripts/fix_branch_attrs.py --model all
    python scripts/fix_branch_attrs.py --model CESM2 --apply
    python scripts/fix_branch_attrs.py --model NorESM2-LM --apply --tipmip-root ~/data/tipmip
    python scripts/fix_branch_attrs.py --model UKESM1-2-LL --apply --include-mlotst
"""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cftime
import netCDF4 as nc
import xarray as xr

DEFAULT_TIPMIP_ROOT = Path.home() / "data/tipmip"
DEFAULT_PARENT_UNITS = "days since 0001-01-01"
DEFAULT_CALENDAR = "noleap"

UKESM_MODEL = "UKESM1-2-LL"
UKESM_INTERNAL_SOURCE_ID = "eUKESM1-1-ice-N96ORCA1"
UKESM_PARENT_UNITS = "days since 1850-01-01"

# Jeremy Walton, Met Office addMetadata.py (16-07-2026).
UKESM_BRANCH_YEAR: dict[str, int] = {
    "esm-piControl": 0,
    "esm-up2p0": 2277,
    "esm-up2p0-gwl2p0": 1944,
    "esm-up2p0-gwl2p0-50y-dn2p0": 1994,
    "esm-up2p0-gwl4p0": 2044,
    "esm-up2p0-gwl4p0-50y-dn2p0": 2094,
    "esm-up2p0-gwl4p0-50y-dn2p0-gwl2p0": 2232,
}

UKESM_PARENT_EXPERIMENT: dict[str, str] = {
    "esm-up2p0": "esm-piControl",
    "esm-up2p0-gwl2p0": "esm-up2p0",
    "esm-up2p0-gwl4p0": "esm-up2p0",
    "esm-up2p0-gwl2p0-50y-dn2p0": "esm-up2p0-gwl2p0",
    "esm-up2p0-gwl4p0-50y-dn2p0": "esm-up2p0-gwl4p0",
    "esm-up2p0-gwl4p0-50y-dn2p0-gwl2p0": "esm-up2p0-gwl4p0-50y-dn2p0",
}

ALL_MODELS = (UKESM_MODEL, "NorESM2-LM", "CESM2")


def experiment_id_from_filename(path: Path, model_id: str) -> str | None:
    parts = path.name.split("_")
    if len(parts) < 4 or parts[2] != model_id:
        return None
    return parts[3]


def _calendar_from_file(path: Path) -> str:
    try:
        with xr.open_dataset(path, decode_times=False) as ds:
            if "time" in ds.coords:
                raw = ds.time.attrs.get("calendar") or ds.time.encoding.get("calendar")
                if raw in (None, "365_day"):
                    return DEFAULT_CALENDAR
                return str(raw)
    except Exception:
        pass
    return DEFAULT_CALENDAR


def _cftime_branch_time(
    branch_year: int, parent_units: str, *, calendar: str = DEFAULT_CALENDAR
) -> float:
    date = cftime.datetime(branch_year, 1, 1, calendar=calendar)
    return float(cftime.date2num(date, units=parent_units, calendar=calendar))


def _decoded_branch_year(
    branch_time: float, parent_units: str, *, calendar: str = DEFAULT_CALENDAR
) -> int:
    date = cftime.num2date(branch_time, units=parent_units, calendar=calendar)
    return int(date.year)


def _ukesm_branch_time(branch_year: int) -> float:
    return float((branch_year - 1850) * 360)


def _skip_name(name: str) -> bool:
    return name.endswith(".bak") or "_original.nc" in name or name.endswith("_anomaly.nc")


def _discover_cftime_files(
    root: Path, *, model_id: str, include_mlotst: bool
) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob(f"*{model_id}*.nc")):
        if _skip_name(path.name):
            continue
        if not include_mlotst and not path.name.startswith("tas_") and "gmstmon" not in path.name:
            continue
        if experiment_id_from_filename(path, model_id) != "esm-up2p0":
            continue
        out.append(path)
    return out


def _discover_ukesm_files(root: Path, *, include_mlotst: bool) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*UKESM*.nc")):
        if _skip_name(path.name):
            continue
        if not include_mlotst and not path.name.startswith("tas_"):
            continue
        exp = experiment_id_from_filename(path, UKESM_MODEL)
        if exp is None or exp not in UKESM_BRANCH_YEAR:
            continue
        out.append(path)
    return out


def _cftime_attrs(
    model_id: str,
    branch_year: int,
    *,
    calendar: str,
    patch_identity: bool,
) -> dict[str, str | float]:
    parent_units = DEFAULT_PARENT_UNITS
    attrs: dict[str, str | float] = {
        "branch_method": "standard",
        "branch_time_in_parent": _cftime_branch_time(
            branch_year, parent_units, calendar=calendar
        ),
        "parent_time_units": parent_units,
        "parent_source_id": model_id,
        "parent_experiment_id": "esm-piControl",
        "parent_variant_label": "r1i1p1f1",
        "parent_activity_id": "CMIP",
    }
    if patch_identity:
        attrs["experiment_id"] = "esm-up2p0"
        attrs["source_id"] = model_id
    return attrs


def _ukesm_attrs(experiment_id: str) -> dict[str, str | float] | None:
    if experiment_id not in UKESM_BRANCH_YEAR:
        return None

    branch_year = UKESM_BRANCH_YEAR[experiment_id]
    out: dict[str, str | float] = {
        "experiment_id": experiment_id,
        "source_id": UKESM_MODEL,
    }
    if branch_year <= 0:
        return out

    parent_experiment_id = UKESM_PARENT_EXPERIMENT.get(experiment_id)
    if parent_experiment_id is None:
        return None

    out.update(
        {
            "branch_method": "standard",
            "branch_time_in_parent": _ukesm_branch_time(branch_year),
            "parent_time_units": UKESM_PARENT_UNITS,
            "parent_source_id": UKESM_INTERNAL_SOURCE_ID,
            "parent_experiment_id": parent_experiment_id,
            "parent_variant_label": "r1i1p1f1",
            "parent_activity_id": "CMIP",
        }
    )
    return out


def _patch_cftime_file(
    path: Path,
    *,
    model_id: str,
    branch_year: int,
    patch_identity: bool,
    apply: bool,
    backup: bool,
) -> bool:
    experiment_id = experiment_id_from_filename(path, model_id)
    if experiment_id != "esm-up2p0":
        return False

    calendar = _calendar_from_file(path)
    new_attrs = _cftime_attrs(
        model_id, branch_year, calendar=calendar, patch_identity=patch_identity
    )

    with nc.Dataset(path, "r") as ds:
        old_bt = getattr(ds, "branch_time_in_parent", None)
        old_units = getattr(ds, "parent_time_units", None) or DEFAULT_PARENT_UNITS
        old_year = (
            _decoded_branch_year(float(old_bt), str(old_units), calendar=calendar)
            if old_bt is not None
            else None
        )
        old_exp = getattr(ds, "experiment_id", None)
        old_src = getattr(ds, "source_id", None)

    attrs_match = old_year == branch_year
    if patch_identity:
        attrs_match = (
            attrs_match
            and str(old_exp or "") == "esm-up2p0"
            and str(old_src or "") == model_id
        )
    if attrs_match:
        return False

    print(f"\n{path}")
    print(f"  experiment {experiment_id}; branch year {old_year!r} -> {branch_year}")
    if patch_identity:
        print(f"  experiment_id/source_id: {old_exp!r}/{old_src!r} -> esm-up2p0/{model_id}")
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


def _patch_ukesm_file(path: Path, *, apply: bool, backup: bool) -> bool:
    experiment_id = experiment_id_from_filename(path, UKESM_MODEL)
    if experiment_id is None:
        print(f"  skip (unrecognised name): {path}")
        return False

    new_attrs = _ukesm_attrs(experiment_id)
    if new_attrs is None:
        print(f"  skip (no patch rule): {path}")
        return False

    with nc.Dataset(path, "r") as ds:
        old = {
            "experiment_id": getattr(ds, "experiment_id", None),
            "source_id": getattr(ds, "source_id", None),
            "branch_time_in_parent": getattr(ds, "branch_time_in_parent", None),
            "parent_experiment_id": getattr(ds, "parent_experiment_id", None),
        }

    branch_year = UKESM_BRANCH_YEAR[experiment_id]
    parent = UKESM_PARENT_EXPERIMENT.get(experiment_id, "(none)")
    print(f"\n{path}")
    print(f"  experiment {experiment_id}; branch year {branch_year} <- {parent}")
    print(f"  was: {old}")
    if branch_year > 0:
        print(f"  new branch_time_in_parent={new_attrs['branch_time_in_parent']}")
    print(f"  new experiment_id/source_id={new_attrs['experiment_id']}/{new_attrs['source_id']}")

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


@dataclass(frozen=True)
class ModelRunner:
    model_id: str
    discover: Callable[[Path, bool], list[Path]]
    patch: Callable[[Path, bool, bool], bool]
    after_apply_hint: str


def _runners() -> dict[str, ModelRunner]:
    return {
        UKESM_MODEL: ModelRunner(
            model_id=UKESM_MODEL,
            discover=lambda root, include_mlotst: _discover_ukesm_files(
                root, include_mlotst=include_mlotst
            ),
            patch=lambda path, apply, backup: _patch_ukesm_file(
                path, apply=apply, backup=backup
            ),
            after_apply_hint="Rebuild UKESM gwlmap_* products and paper figures "
            "(python paper/build_all.py).",
        ),
        "NorESM2-LM": ModelRunner(
            model_id="NorESM2-LM",
            discover=lambda root, include_mlotst: _discover_cftime_files(
                root, model_id="NorESM2-LM", include_mlotst=include_mlotst
            ),
            patch=lambda path, apply, backup: _patch_cftime_file(
                path,
                model_id="NorESM2-LM",
                branch_year=1851,
                patch_identity=False,
                apply=apply,
                backup=backup,
            ),
            after_apply_hint="Then rebuild gmstmon (if tas patched), NorESM gwlmap_* "
            "products, and paper figures (python paper/build_all.py).",
        ),
        "CESM2": ModelRunner(
            model_id="CESM2",
            discover=lambda root, include_mlotst: _discover_cftime_files(
                root, model_id="CESM2", include_mlotst=include_mlotst
            ),
            patch=lambda path, apply, backup: _patch_cftime_file(
                path,
                model_id="CESM2",
                branch_year=81,
                patch_identity=True,
                apply=apply,
                backup=backup,
            ),
            after_apply_hint="Then rebuild CESM2 gwlmap_* products and paper figures "
            "(python paper/build_all.py).",
        ),
    }


def _selected_models(model_arg: str) -> list[str]:
    if model_arg == "all":
        return list(ALL_MODELS)
    if model_arg not in ALL_MODELS:
        raise SystemExit(f"Unknown model {model_arg!r}; choose from {ALL_MODELS} or 'all'.")
    return [model_arg]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=[*ALL_MODELS, "all"],
        default="all",
        help="model to patch (default: all)",
    )
    parser.add_argument("--tipmip-root", type=Path, default=DEFAULT_TIPMIP_ROOT)
    parser.add_argument(
        "--apply", action="store_true", help="write attrs (default: dry run)"
    )
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument(
        "--include-mlotst",
        action="store_true",
        help="also patch raw mlotst files (default: tas/gmstmon or tas only for UKESM)",
    )
    args = parser.parse_args()

    root = args.tipmip_root.expanduser()
    mode = "APPLY" if args.apply else "DRY RUN"
    runners = _runners()
    hints: list[str] = []

    print(f"=== fix_branch_attrs ({mode}) ===")
    print(f"tipmip root: {root}")

    for model_id in _selected_models(args.model):
        runner = runners[model_id]
        print(f"\n--- {model_id} ---")
        files = runner.discover(root, args.include_mlotst)
        if not files:
            print(f"No matching {model_id} files found.")
            continue

        n_patch = sum(
            1
            for path in files
            if runner.patch(path, args.apply, not args.no_backup)
        )
        print(f"Summary: {n_patch} file(s) to patch.")
        if n_patch and not args.apply:
            hints.append(runner.after_apply_hint)

    if not args.apply and hints:
        print("\nRe-run with --apply to write changes.")
        for hint in dict.fromkeys(hints):
            print(hint)


if __name__ == "__main__":
    main()
