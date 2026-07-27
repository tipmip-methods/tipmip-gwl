# HPC scripts (GMSAT / temperature mapping)

Shell helpers for preparing **`gmstmon`** files and pulling them from Levante.
The mapping algorithm lives in `src/tipmip_gwl/`; these scripts are for data
staging on DKRZ / PIK.

## Recommended workflow

On **Levante** (after `pip install -e .` and `module load cdo`):

```bash
sbatch scripts/run_preprocess_levante.slurm
# output: /work/bm1448/analysis/harteg/merged/tas/<exp>/gmstmon/
```

Or interactively:

```bash
python scripts/build_gmstmon.py --exp esm-piControl \
  --outdir /work/bm1448/analysis/harteg/merged/tas/esm-piControl/gmstmon
```

(`--manifest` defaults to `scripts/data/tas_chunks.tsv`.)

Copy to laptop (skip PIK for these tiny files):

```bash
rsync -avP user@levante.dkrz.de:.../gmstmon/ ~/Desktop/tipmip/tas/esm-piControl/gmstmon/
```

Optional PIK staging: `pull_gmstmon_pik.sh` + `run_pull_gmstmon.slurm`.

Then build GWL maps:

```bash
tipmip-gwl-build --leg ramp-up \
  --up2p0-dir ... --picontrol-dir ... --outdir mapping/

# ramp-down (or: tipmip-gwl-build-rampdown --dn-dir ... ...)
tipmip-gwl-build --leg ramp-down \
  --dn-dir ... --picontrol-dir ... --outdir mapping/
```

## Files

| Script | Where to run | Purpose |
|--------|--------------|---------|
| `build_gmstmon.py` | Levante / local | Merge raw tas chunks → monthly gmstmon |
| `run_diagnostics.py` | Local | Sanity table for staged ramp-up gmstmon |
| `run_preprocess_levante.slurm` | Levante | Batch gmstmon build for piControl + ramp-up |
| `pull_gmstmon_pik.sh` | PIK | Rsync `gmstmon/` from Levante to PIK scratch |
| `pull_gmstmon_local.sh` | Laptop | Rsync `gmstmon/` from Levante to `~/Desktop/tipmip/tas/` |
| `prepare_rampdown_merge.py` | Local | Build merge lists for ramp-down experiments |
| `run_pull_gmstmon.slurm` | PIK | Slurm wrapper for the pull script |
| `sync_bundled_mappings.py` | Local | Copy rebuilt `mapping/` into package data |

Path manifest: **`scripts/data/tas_chunks.tsv`** — edit when Levante paths move.

Full documentation: **`docs/gmstmon_pipeline.md`**.
