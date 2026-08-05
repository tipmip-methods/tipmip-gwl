# Building mapping products

For **maintainers** regenerating `gwlmap_*.nc` from staged gmstmon. End users:
[using_mappings.md](using_mappings.md).

## Included ensemble

```python
from tipmip_gwl import INCLUDED_MODELS
```

(`src/tipmip_gwl/ensemble.py` — also drives paper figures and builds.)

`tipmip-gwl-build` and paper scripts **only process included models**. Extra
gmstmon in staging for models outside ``INCLUDED_MODELS`` is ignored. Missing
data for any included model raises `MissingEnsembleDataError`.

Staged layout: [staged_data.md](staged_data.md).

## Algorithm (three steps)

1. GMSAT anomaly vs 31-yr branch-window piControl baseline (full mean when branch
   metadata is missing or out of span)
2. 31-yr centred running mean + isotonic regression (PAVA)
3. Invert to common GWL grid → `year_of_gwl`, forward map → `gwl_axis`

Annual GMSAT uses days-in-month weighting on read (`load_gmsat_nc`).

## Preprocess gmstmon (tas → monthly GMSAT)

Skip if gmstmon is already staged under `~/data/tipmip/tas/`.

```bash
python scripts/build_gmstmon.py \
  --manifest /path/to/tas_chunks.tsv \
  --exp esm-piControl \
  --outdir ~/data/tipmip/tas/esm-piControl/gmstmon
```

Manifest: TSV columns `model`, `experiment_id`, `path` (required via `--manifest`; no
default shipped in this repo).

Output: `<outdir>/tas_*_<model>_<exp>_gmstmon.nc`. Do **not** use `cdo yearmean` for
the mapping baseline — annual means are computed on read with days-in-month weighting.

| Topic | Detail |
|-------|--------|
| Duplicate months | Dropped after chunk merge |
| Backend | `auto` (CDO if installed) or `xarray` |
| UKESM attrs | Patch branch year: `scripts/fix_ukesm_branch_attrs.py --apply` |
| NorESM attrs | Patch branch year 1851: `scripts/fix_noresm_branch_attrs.py --apply` |

Other helpers: `scripts/fix_ukesm_branch_attrs.py`, `scripts/fix_noresm_branch_attrs.py`
— see [scripts/README.md](../scripts/README.md).

## Build mappings

Default output: ``mapping/`` in this repository (override with ``--outdir`` or
``TIPMIP_GWL_MAPPINGS``).

```bash
pip install -e ".[paper]"

tipmip-gwl-build \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon
```

Ramp-down (repeat for 2 °C and 4 °C legs):

```bash
tipmip-gwl-build --leg ramp-down \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon
```

Optional sanity table: `python paper/helper_diagnostics.py --up2p0-dir ... --picontrol-dir ...`

## Python API

```python
from tipmip_gwl.build import write_products, write_rampdown_products
from tipmip_gwl.product import default_mappings_dir

out = default_mappings_dir()
write_products(up2p0_dir, picontrol_dir, out)
write_rampdown_products(dn_dir, picontrol_dir, out)
```

Pass `models=(...)` to override the ensemble for isolated tests only.
