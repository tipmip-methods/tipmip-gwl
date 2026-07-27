# Building mapping products

This guide is for **maintainers** who regenerate the `gwlmap_*.nc` coordinate
products from staged TIPMIP tas. End users who only want to resample their own
diagnostics should install the package and follow
[using_mappings.md](using_mappings.md) instead.

## Overview

The mapping pipeline has three steps, applied identically to every model:

1. **Anomaly computation** — weighted annual-mean GMSAT, 31-yr branch-window
   piControl baseline (full mean when branch metadata is missing or out of span)
2. **Smoothing and monotonicity** — 31-year centred running mean, then isotonic
   (PAVA) regression
3. **Inversion** — store `year_of_gwl(gwl)` on the common 0–4 °C grid and
   `gwl_axis(year)` on the native year axis

Archive preprocessing builds monthly `gmstmon` from raw `tas`; the
days-in-month-weighted annual mean is applied on read (Step 1). See
[gmstmon_pipeline.md](gmstmon_pipeline.md) for preprocessing detail.

## Quick start (rebuild locally)

```bash
conda activate toad312
pip install -e ".[paper]"

# 1. Stage gmstmon (if not already on disk)
python scripts/build_gmstmon.py --exp esm-piControl --outdir ~/Desktop/tipmip/tas/esm-piControl/gmstmon
python scripts/build_gmstmon.py --exp esm-up2p0       --outdir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon

# 2. Optional sanity table
python scripts/run_diagnostics.py \
  --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon

# Optional piControl figure: python paper/figures_1_2.py ...

# 3. Build mapping products
tipmip-gwl-build \
  --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

Output: one NetCDF per mappable model under `mapping/`, named
`gwlmap_<model>_esm-up2p0_v1.nc`.

A model is skipped only when it has no matching piControl tas on disk. Other
provenance issues are recorded as warnings on the file; the model is still mapped
when possible.

## Published baseline

The published baseline is the **31-yr mean centred on the branch year**
(trailing first 31 years when the branch is at piControl start). Models with
missing or out-of-span branch years fall back to the **full piControl mean**
(NorESM2-LM). For the staged ensemble, |full mean − branch window| is at most
~0.09 K — see `paper/baseline_sensitivity.py`.

## Sync bundled mappings (release step)

End users load mappings via `load_mapping(model)` from package data shipped at
`src/tipmip_gwl/data/mappings/`. After rebuilding `mapping/` locally, refresh
the bundled snapshot before tagging a release:

```bash
python scripts/sync_bundled_mappings.py
# copies 24 publishable v1 files (8 ramp-up + 16 ramp-down) into
# src/tipmip_gwl/data/mappings/
```

The sync script copies **ramp-up and ramp-down legs only** (Tier-1 ensemble,
mapping version `v1`). Zero-emission-hold mappings in `mapping/` are left out —
they are not part of the v1 user product.

Commit the updated `.nc` files so `pip install tipmip-gwl` carries the new
ensemble.

## Product file contents

Each `gwlmap_*.nc` includes:

- `year_of_gwl(gwl)` — model year at each GWL on the common grid (NaN beyond range)
- `gwl_axis(year)` — forward GWL(t) on the native year axis
- `gmsat_anomaly(year)`, `gmsat_anomaly_smoothed(year)`
- Scalars: `baseline_gmsat`, `branch_year`, `picontrol_drift`, `monotonization_max`,
  `max_gwl_reached`, `baseline_method`
- Provenance: input `tracking_id`s, parent run, code version, git revision,
  `mapping_version`

## Other protocol legs

Ramp-down mappings use `tipmip-gwl-build-rampdown` and are bundled with the
package (see sync step above). Zero-emission-hold characterisation is
**exploratory** — see `exploratory/zehold/` (not installed, not bundled).

## Python API (building)

```python
from tipmip_gwl.build import build_mapping_dataset, write_mapping, write_products

written, skipped = write_products(up2p0_dir, picontrol_dir, "mapping/")
```

## Further reading

- [gmstmon_pipeline.md](gmstmon_pipeline.md) — tas → gmstmon preprocessing
- [using_mappings.md](using_mappings.md) — applying mappings downstream
- [paper_figures.md](paper_figures.md) — reproducing figures that use these mappings
- [../scripts/README.md](../scripts/README.md) — Levante / PIK staging helpers
