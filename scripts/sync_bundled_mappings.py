#!/usr/bin/env python3
"""Copy published ramp-up mapping files into the package data directory.

Run after ``tipmip-gwl-build`` when refreshing the ensemble shipped with
``pip install tipmip-gwl``. See ``docs/building_mappings.md``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO_ROOT / "mapping"
DEFAULT_DST = REPO_ROOT / "src" / "tipmip_gwl" / "data" / "mappings"
RAMPUP_SUFFIX = "_esm-up2p0_v1.nc"


def main(src_dir: Path, dst_dir: Path, *, dry_run: bool = False) -> int:
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    if not src_dir.is_dir():
        raise SystemExit(f"source directory not found: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(src_dir.glob(f"gwlmap_*{RAMPUP_SUFFIX}")):
        target = dst_dir / path.name
        if dry_run:
            print(f"would copy {path.name}")
        else:
            shutil.copy2(path, target)
            print(f"copied {path.name}")
        copied += 1

    if copied == 0:
        print(f"no ramp-up v1 mappings found in {src_dir}")
        return 1
    print(f"{copied} file(s) -> {dst_dir}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync ramp-up v1 gwlmap_*.nc files into package data."
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(main(args.src, args.dst, dry_run=args.dry_run))
