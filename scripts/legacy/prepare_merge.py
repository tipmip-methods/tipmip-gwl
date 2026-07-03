#!/usr/bin/env python3
"""Build per-model file lists + manifest for merging a variable on Levante.

Generic over variable (see VAR_CONFIG). Writes lists to
merge_lists/<var>/<exp>/ and a manifest.tsv describing the merge and the
recommended on-Levante reduction (so large fields never get transferred).

Examples
--------
    python3 prepare_merge.py --var tas --exp esm-up2p0
    python3 prepare_merge.py --var tas --exp esm-piControl
    python3 prepare_merge.py --var mlotst --exp esm-piControl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# Primary ensemble member per model (shared across variables here).
MODELS = {
    "ACCESS-ESM1-5": "r1i1p1f1",
    "EC-Earth3-ESM-1": "r1i1p1f1",
    "GFDL-ESM2M": "r1i1p1f1",
    "GISS-E2-1-G-CC2": "r1i1p1f3",
    "IPSL-CM6-ESMCO2": "r1i2p3f1",
    "MIROC-ES2L": "r1i1p1f1",
    "NorESM2-LM": "r1i1p1f1",
    "UKESM1-2-LL": "r1i1p1f1",
}

# Per-variable config: allowed (monthly) tables in preference order, and the
# default on-Levante reduction applied before transfer.
#   reduce="gmstmon" -> cdo -fldmean   (monthly area-weighted global mean;
#                       days-in-month weighted ANNUAL mean done later in Python)
#   reduce="gmst"    -> cdo -yearmean -fldmean   (legacy unweighted annual mean)
#   reduce="yearmax" -> cdo yearmax              (annual maximum field)
#   reduce="none"    -> keep merged monthly field
VAR_CONFIG = {
    "tas": {"tables": ["Amon", "APmon"], "reduce": "gmstmon"},
    "mlotst": {"tables": ["OPmon", "Omon", "Eday"], "reduce": "yearmax"},
}

REDUCE_SUFFIX = {
    "gmstmon": "gmstmon",
    "gmst": "gmst",
    "yearmax": "annualmax",
    "none": "merged",
}


def select_files(df, var, model, exp, member, allowed_tables):
    sub = df[
        (df["var"] == var)
        & (df["model"] == model)
        & (df["exp"] == exp)
        & (df["member"] == member)
        & (df["table"].isin(allowed_tables))
    ].copy()
    if sub.empty:
        return sub

    present = sub["table"].value_counts()
    table = min(present.index, key=lambda t: allowed_tables.index(t))
    sub = sub[sub["table"] == table]
    sub["tstart"] = sub["path"].str.extract(r"_(\d{6,8})-\d{6,8}\.nc$")[0]
    return sub.sort_values("tstart")


def fname(row, var, exp, suffix):
    return "{var}_{table}_{model}_{exp}_{member}_{grid}_{suffix}.nc".format(
        var=var,
        table=row["table"],
        model=row["model"],
        exp=exp,
        member=row["member"],
        grid=row["grid"],
        suffix=suffix,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--var", required=True, choices=sorted(VAR_CONFIG))
    parser.add_argument("--exp", default="esm-up2p0")
    parser.add_argument(
        "--reduce", default=None, choices=["gmstmon", "gmst", "yearmax", "none"]
    )
    parser.add_argument(
        "--inventory",
        default=str(
            Path(__file__).resolve().parents[3] / "inventory" / "inventory_files.tsv"
        ),
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    cfg = VAR_CONFIG[args.var]
    reduce = args.reduce or cfg["reduce"]
    out_dir = Path(args.out_dir or (Path(__file__).parent / "merge_lists" / args.var / args.exp))
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.inventory, sep="\t")
    rows = []
    for model, member in MODELS.items():
        sub = select_files(df, args.var, model, args.exp, member, cfg["tables"])
        if sub.empty:
            print(f"WARNING: no {args.var} for {model} ({args.exp})")
            continue

        meta = sub.iloc[0]
        list_path = out_dir / f"{model}.txt"
        sub["path"].to_csv(list_path, index=False, header=False)
        rows.append(
            {
                "model": model,
                "exp": args.exp,
                "member": meta["member"],
                "table": meta["table"],
                "grid": meta["grid"],
                "n_files": len(sub),
                "filelist": list_path.name,
                "merged_outfile": fname(meta, args.var, args.exp, "merged"),
                "reduce": reduce,
                "reduced_outfile": fname(meta, args.var, args.exp, REDUCE_SUFFIX[reduce]),
            }
        )
        print(f"{model:16s} {meta['table']:6s} {len(sub):4d} files -> {rows[-1]['reduced_outfile']}")

    manifest = pd.DataFrame(rows)
    manifest_path = out_dir / "manifest.tsv"
    manifest.to_csv(manifest_path, sep="\t", index=False)
    print(f"\nWrote {len(manifest)} model lists + manifest to {out_dir}")


if __name__ == "__main__":
    main()
