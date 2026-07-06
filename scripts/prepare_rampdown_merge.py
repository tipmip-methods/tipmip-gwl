#!/usr/bin/env python3
"""Build Levante merge lists for TIPMIP ramp-down tas (gmstmon).

Primary tier-1 ramp-down from +2°C after 50 years of zero emissions:
``esm-up2p0-gwl2p0-50y-dn2p0``. NorESM2-LM uses ``esm-up2p0-swl2p0-50y-dn2p0``.

Writes ``merge_lists/tas/<exp>/`` for ``merge_var.sh`` on Levante.

Example (local, then rsync lists to Levante)::

    python scripts/prepare_rampdown_merge.py \\
      --inventory ../phd-toad/TIPMIP/inventory/inventory_files.tsv \\
      --out-dir /tmp/tas_dn2p0_merge_lists

    rsync -av /tmp/tas_dn2p0_merge_lists/ \\
      user@levante.dkrz.de:/work/bm1448/analysis/harteg/merge_lists/tas/esm-up2p0-gwl2p0-50y-dn2p0/
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Reuse the legacy merge-list builder shipped with tipmip-gwl.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "legacy"))
from prepare_merge import MODELS, REDUCE_SUFFIX, VAR_CONFIG, fname, select_files  # noqa: E402

PRIMARY_EXP = "esm-up2p0-gwl2p0-50y-dn2p0"
NORESM_EXP = "esm-up2p0-swl2p0-50y-dn2p0"


def _write_manifest_row(rows, model, meta, exp, out_dir, reduce):
    list_path = out_dir / f"{model}.txt"
    return {
        "model": model,
        "exp": exp,
        "member": meta["member"],
        "table": meta["table"],
        "grid": meta["grid"],
        "n_files": len(rows),
        "filelist": list_path.name,
        "merged_outfile": fname(meta, "tas", exp, "merged"),
        "reduce": reduce,
        "reduced_outfile": fname(meta, "tas", exp, REDUCE_SUFFIX[reduce]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("merge_lists/tas") / PRIMARY_EXP,
    )
    parser.add_argument("--reduce", default="gmstmon", choices=["gmstmon", "gmst"])
    args = parser.parse_args()

    import pandas as pd

    df = pd.read_csv(args.inventory, sep="\t")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []

    for model, member in MODELS.items():
        exp = NORESM_EXP if model == "NorESM2-LM" else PRIMARY_EXP
        sub = select_files(df, "tas", model, exp, member, VAR_CONFIG["tas"]["tables"])
        if sub.empty:
            print(f"WARNING: no tas for {model} ({exp})")
            continue
        meta = sub.iloc[0]
        list_path = args.out_dir / f"{model}.txt"
        sub["path"].to_csv(list_path, index=False, header=False)
        manifest_rows.append(
            _write_manifest_row(sub, model, meta, exp, args.out_dir, args.reduce)
        )
        print(
            f"{model:16s} {meta['table']:6s} {len(sub):4d} files -> "
            f"{manifest_rows[-1]['reduced_outfile']}"
        )

    manifest_path = args.out_dir / "manifest.tsv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, sep="\t", index=False)
    print(f"\nWrote {len(manifest_rows)} model lists + manifest to {args.out_dir}")


if __name__ == "__main__":
    main()
