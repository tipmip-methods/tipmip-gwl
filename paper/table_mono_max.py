"""
Build the SI monotonization table: per-model ``mono_max`` for each mapping leg.

Reads ``monotonization_max`` from the bundled ``gwlmap_*.nc`` products (the
same scalar shipped in each mapping file). This is separate from Table A1
(``table1.py``), which covers baseline-reference diagnostics.

Usage::

    python paper/table_mono_max.py \\
        --mapping-dir mapping \\
        --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \\
        --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import xarray as xr
from mlotst_remap_helpers import bundled_models, mapping_index_by_leg
from table1 import model_order_by_ref_full

DEFAULT_OUT_CSV = Path(__file__).resolve().parent / "tables" / "table_mono_max.csv"

LEGS = (
    ("ramp-up", "mono_max_ramp_up_degC"),
    ("ramp-down-2c", "mono_max_ramp_down_2c_degC"),
    ("ramp-down-4c", "mono_max_ramp_down_4c_degC"),
)

FIELDNAMES = ("model",) + tuple(col for _, col in LEGS)


def _r3(x):
    return None if x is None else round(float(x), 3)


def _mono_max_by_model(mapping_dir: Path, leg: str) -> dict[str, float]:
    out: dict[str, float] = {}
    allowed = set(bundled_models())
    for model, path in mapping_index_by_leg(mapping_dir, leg).items():
        if model not in allowed:
            continue
        with xr.open_dataset(path) as ds:
            out[model] = float(ds["monotonization_max"].values)
    return out


def main(mapping_dir, up2p0_dir=None, picontrol_dir=None, window=31, out_csv=None):
    mapping_dir = Path(mapping_dir)
    by_leg = {leg: _mono_max_by_model(mapping_dir, leg) for leg, _ in LEGS}
    all_models = set().union(*by_leg.values())
    if up2p0_dir is not None and picontrol_dir is not None:
        order = model_order_by_ref_full(up2p0_dir, picontrol_dir, window=window)
        models = [m for m in order if m in all_models]
        extra = sorted(all_models - set(models))
        models = models + extra
    else:
        models = sorted(all_models)

    rows = []
    for model in models:
        row = {"model": model}
        for leg, col in LEGS:
            row[col] = _r3(by_leg[leg].get(model))
        rows.append(row)

    hdr = f"{'model':<22} {'mono_up':>9} {'mono_dn2c':>10} {'mono_dn4c':>10}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        vals = []
        for _, col in LEGS:
            v = r[col]
            vals.append(f"{v:10.3f}" if v is not None else f"{'-':>10}")
        print(f"{r['model']:<22} {vals[0]} {vals[1]} {vals[2]}")

    for leg, col in LEGS:
        present = [r[col] for r in rows if r[col] is not None]
        if present:
            print(f"\nmax {col} = {max(present):.3f} degC ({len(present)} models)")

    out_csv = Path(out_csv) if out_csv else DEFAULT_OUT_CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build per-model monotonization_max table for all legs."
    )
    parser.add_argument(
        "--mapping-dir",
        default=str(Path(__file__).resolve().parent.parent / "mapping"),
        help="directory of gwlmap_*.nc mapping products",
    )
    parser.add_argument(
        "--up2p0-dir",
        default=None,
        help="ramp-up gmstmon dir (same as table1.py; sets model row order)",
    )
    parser.add_argument(
        "--picontrol-dir",
        default=None,
        help="piControl gmstmon dir (same as table1.py; sets model row order)",
    )
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    args = parser.parse_args()
    main(
        args.mapping_dir,
        up2p0_dir=args.up2p0_dir,
        picontrol_dir=args.picontrol_dir,
        window=args.window,
        out_csv=args.out_csv,
    )
