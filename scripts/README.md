# HPC scripts (GMSAT / temperature mapping)

Shell helpers for preparing **`gmstmon`** files on Levante and pulling merged
products to your local staging tree. The mapping algorithm lives in
`src/tipmip_gwl/`.

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

Pull to laptop:

```bash
export TIPMIP_EXP=esm-piControl   # or esm-up2p0, ramp-down experiment id, ...
bash scripts/pull_gmstmon_local.sh
# -> ~/data/tipmip/tas/<exp>/gmstmon/
```

Then build GWL maps locally:

```bash
tipmip-gwl-build --leg ramp-up \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/

tipmip-gwl-build --leg ramp-down \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

## Files

| Script | Where to run | Purpose |
|--------|--------------|---------|
| `build_gmstmon.py` | Levante / local | Merge raw tas chunks → monthly gmstmon |
| `run_diagnostics.py` | Local | Sanity table for staged ramp-up gmstmon |
| `run_preprocess_levante.slurm` | Levante | Batch gmstmon build for piControl + ramp-up |
| `pull_gmstmon_local.sh` | Laptop | Rsync `gmstmon/` from Levante to `~/data/tipmip/tas/` |
| `prepare_rampdown_merge.py` | Local | Build merge lists for ramp-down experiments |
| `sync_bundled_mappings.py` | Local | Copy rebuilt `mapping/` into package data |

Path manifest: **`scripts/data/tas_chunks.tsv`** — edit when Levante paths move.

Full documentation: **`docs/gmstmon_pipeline.md`**.
