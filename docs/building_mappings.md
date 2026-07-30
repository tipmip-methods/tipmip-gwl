# Building mapping products

For **maintainers** regenerating `gwlmap_*.nc` from staged gmstmon. End users:
[using_mappings.md](using_mappings.md).

## Pipeline (three steps)

1. GMSAT anomaly vs 31-yr branch-window piControl baseline (full mean when branch
   metadata is missing or out of span)
2. 31-yr centred running mean + isotonic regression (PAVA)
3. Invert to common GWL grid → `year_of_gwl`, forward map → `gwl_axis`

Annual GMSAT uses days-in-month weighting on read (`load_gmsat_nc`). Preprocess tas
with [gmstmon_pipeline.md](gmstmon_pipeline.md).

## Quick start

```bash
conda activate toad312
pip install -e ".[paper]"

python scripts/build_gmstmon.py --exp esm-piControl --outdir ~/data/tipmip/tas/esm-piControl/gmstmon
python scripts/build_gmstmon.py --exp esm-up2p0       --outdir ~/data/tipmip/tas/esm-up2p0/gmstmon

tipmip-gwl-build \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

Ramp-down: `tipmip-gwl-build-rampdown` with `--dn-dir` pointing at ramp-down gmstmon.

A model is skipped only without matching piControl tas; other provenance issues are
warnings on the output file.

Optional sanity table: `python scripts/run_diagnostics.py --up2p0-dir ... --picontrol-dir ...`

## Sync bundled mappings (release)

After rebuilding `mapping/`:

```bash
python scripts/sync_bundled_mappings.py
```

Copies 24 publishable v1 files (8 ramp-up + 16 ramp-down) into
`src/tipmip_gwl/data/mappings/`. Zero-emission-hold products are excluded.

## Python API

```python
from tipmip_gwl.build import write_products, write_rampdown_products

write_products(up2p0_dir, picontrol_dir, "mapping/")
write_rampdown_products(dn_dir, picontrol_dir, "mapping/")
```

Zero-emission-hold mapping is exploratory only: `exploratory/zehold/`.
