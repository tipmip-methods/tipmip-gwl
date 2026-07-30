# GMSAT preprocessing (tas → gmstmon)

Maintainer step before [building_mappings.md](building_mappings.md). End users can skip this.

**Tool:** `python scripts/build_gmstmon.py`  
**Manifest:** `scripts/data/tas_chunks.tsv` (Levante chunk paths; edit when paths move)

## Output layout

Monthly area-weighted global-mean tas, one file per model:

```text
<outdir>/tas_*_<model>_<exp>_gmstmon.nc
```

Example: `~/data/tipmip/tas/esm-up2p0/gmstmon/`

Days-in-month-weighted **annual** GMSAT is applied on read by `load_gmsat_nc` — do not
use `cdo yearmean` for the mapping baseline.

## Commands

```bash
conda activate toad312
pip install -e ".[paper]"

# All models, one experiment (Levante or local chunks via manifest)
python scripts/build_gmstmon.py --exp esm-piControl --outdir /path/to/gmstmon

# One model
python scripts/build_gmstmon.py --exp esm-up2p0 --models GFDL-ESM2M --outdir ./gmstmon

# Explicit chunk list (no manifest)
python scripts/build_gmstmon.py --chunks chunk1.nc chunk2.nc --out path/to/out.nc
```

Other experiments (ramp-down, etc.): same command with the matching `--exp` /
`experiment_id` from `tas_chunks.tsv`. NorESM ramp-down uses `esm-up2p0-swl2p0-50y-dn2p0`.

Pull merged gmstmon to your laptop:

```bash
export TIPMIP_EXP=esm-piControl
bash scripts/pull_gmstmon_local.sh
```

HPC preprocess batch: `scripts/run_preprocess_levante.slurm`. More helpers: `scripts/README.md`.

## Notes

| Topic | Detail |
|-------|--------|
| Duplicate months | Dropped after chunk merge; avoid overlapping chunk ranges in the manifest |
| Backend | `auto` (CDO if installed) or `xarray`; spatial mean at preprocess, annual mean on read |
| mlotst | Not handled here |

After gmstmon is staged, run `tipmip-gwl-build` — see [building_mappings.md](building_mappings.md).
