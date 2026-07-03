# HPC scripts (GMSAT / temperature mapping)

Shell helpers for preparing **`gmstmon`** files and pulling them from Levante.
The mapping algorithm itself lives in `src/tipmip_gwl/`; these scripts are for
data staging on DKRZ / PIK.

## Recommended workflow

On **Levante** (after `pip install -e .` and `module load cdo`):

```bash
sbatch scripts/run_preprocess_levante.slurm
# output: /work/bm1448/analysis/harteg/merged/tas/<exp>/gmstmon/
```

Or interactively:

```bash
tipmip-gwl-preprocess --exp esm-piControl \
  --outdir /work/bm1448/analysis/harteg/merged/tas/esm-piControl/gmstmon
```

(`--manifest` defaults to the bundled `src/tipmip_gwl/data/tas_chunks.tsv`.)

Copy to laptop (skip PIK for these tiny files):

```bash
rsync -avP user@levante.dkrz.de:.../gmstmon/ ~/Desktop/tipmip/tas/esm-piControl/gmstmon/
```

Optional PIK staging: `pull_gmstmon_pik.sh` + `run_pull_gmstmon.slurm`.

Then build GWL maps:

```bash
tipmip-gwl-build --up2p0-dir ... --picontrol-dir ... --outdir mapping/
```

## Files

| Script | Where to run | Purpose |
|--------|--------------|---------|
| `run_preprocess_levante.slurm` | Levante | Batch `tipmip-gwl-preprocess` for both experiments |
| `pull_gmstmon_pik.sh` | PIK | Rsync `gmstmon/` from Levante to PIK scratch |
| `run_pull_gmstmon.slurm` | PIK | Slurm wrapper for the pull script |
| `legacy/` | Levante | Superseded CDO merge pipeline (`merge_var.sh`, …) |

Path manifest: **`src/tipmip_gwl/data/tas_chunks.tsv`** — edit when Levante paths move.

Full documentation: **`docs/gmstmon_pipeline.md`**.
