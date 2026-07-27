#!/usr/bin/env python3
"""Copy published mapping files into the package data directory.

Syncs ramp-up and ramp-down legs (24 files for the Tier-1 ensemble). Zero-emission
hold mappings are excluded — they are not part of the v1 user product.

Run after rebuilding ``mapping/`` locally, before tagging a release. See
``docs/building_mappings.md``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO_ROOT / "mapping"
DEFAULT_DST = REPO_ROOT / "src" / "tipmip_gwl" / "data" / "mappings"

sys.path.insert(0, str(REPO_ROOT / "src"))

from tipmip_gwl.product import (  # noqa: E402
    DEFAULT_MAPPING_VERSION,
    LEG_RAMP_DOWN_2C,
    LEG_RAMP_DOWN_4C,
    LEG_RAMP_UP,
    _experiment_bundle_priority,
    _leg_for_experiment,
    _parse_mapping_filename,
)

BUNDLE_LEGS = (LEG_RAMP_UP, LEG_RAMP_DOWN_2C, LEG_RAMP_DOWN_4C)


def publishable_mapping_paths(src_dir: Path) -> list[Path]:
    """Return sorted ``gwlmap_*.nc`` paths that ship with the package."""
    by_model_leg: dict[tuple[str, str], Path] = {}
    for path in sorted(src_dir.glob("gwlmap_*.nc")):
        parsed = _parse_mapping_filename(path)
        if parsed is None:
            continue
        model, experiment, version = parsed
        if version != DEFAULT_MAPPING_VERSION:
            continue
        leg = _leg_for_experiment(experiment)
        if leg is None:
            continue
        key = (model, leg)
        existing = by_model_leg.get(key)
        if existing is None:
            by_model_leg[key] = path
            continue
        existing_experiment = _parse_mapping_filename(existing)[1]
        if _experiment_bundle_priority(experiment) < _experiment_bundle_priority(
            existing_experiment
        ):
            by_model_leg[key] = path
    return sorted(by_model_leg.values())


def main(
    src_dir: Path,
    dst_dir: Path,
    *,
    dry_run: bool = False,
    prune: bool = True,
) -> int:
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    if not src_dir.is_dir():
        raise SystemExit(f"source directory not found: {src_dir}")

    publishable = publishable_mapping_paths(src_dir)
    if not publishable:
        print(f"no publishable v1 mappings found in {src_dir}")
        return 1

    publishable_names = {p.name for p in publishable}
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for path in publishable:
        target = dst_dir / path.name
        if dry_run:
            print(f"would copy {path.name}")
        else:
            shutil.copy2(path, target)
            print(f"copied {path.name}")
        copied += 1

    removed = 0
    if prune and dst_dir.is_dir():
        for existing in sorted(dst_dir.glob("gwlmap_*.nc")):
            if existing.name in publishable_names:
                continue
            if dry_run:
                print(f"would remove stale {existing.name}")
            else:
                existing.unlink()
                print(f"removed stale {existing.name}")
            removed += 1

    leg_counts = {leg: 0 for leg in BUNDLE_LEGS}
    for path in publishable:
        experiment = _parse_mapping_filename(path)[1]
        leg = _leg_for_experiment(experiment)
        if leg is not None:
            leg_counts[leg] += 1

    summary = ", ".join(f"{leg}={leg_counts[leg]}" for leg in BUNDLE_LEGS)
    action = "would sync" if dry_run else "synced"
    print(f"{action} {copied} file(s) ({summary}) -> {dst_dir}")
    if removed:
        stale_action = "would remove" if dry_run else "removed"
        print(f"{stale_action} {removed} stale file(s) from bundle")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync ramp-up and ramp-down v1 gwlmap_*.nc files into package data."
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="leave stale .nc files in the bundle directory",
    )
    args = parser.parse_args()
    raise SystemExit(
        main(args.src, args.dst, dry_run=args.dry_run, prune=not args.no_prune)
    )
