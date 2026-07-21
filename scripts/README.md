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

For ramp-down or ZE-hold legs, use the same command with the appropriate
`--exp` (paths are already in `tas_chunks.tsv`). See `docs/gmstmon_pipeline.md`.

Copy to laptop (skip PIK for these tiny files):

```bash
rsync -avP user@levante.dkrz.de:.../gmstmon/ ~/Desktop/tipmip/tas/esm-piControl/gmstmon/
```

Optional PIK staging: `pull_gmstmon_pik.sh` + `run_pull_gmstmon.slurm`.

Then build GWL maps and optionally refresh the bundled release snapshot:

```bash
tipmip-gwl-build --up2p0-dir ... --picontrol-dir ... --outdir mapping/
python scripts/sync_bundled_mappings.py   # copy ramp-up v1 -> package data
```

See **`docs/building_mappings.md`** for the full maintainer workflow.

## Files

| Script | Where to run | Purpose |
|--------|--------------|---------|
| `run_preprocess_levante.slurm` | Levante | Batch `tipmip-gwl-preprocess` for ramp-up + piControl |
| `pull_gmstmon_pik.sh` | PIK | Rsync `gmstmon/` from Levante to PIK scratch |
| `pull_gmstmon_local.sh` | Laptop | Rsync `gmstmon/` from Levante to `~/Desktop/tipmip/tas/` |
| `patch_ukesm_branch_attrs.py` | Local | Write CMIP branch metadata onto UKESM gmstmon files (see script docstring) |
| `sync_bundled_mappings.py` | Local | Copy `mapping/gwlmap_*_esm-up2p0_v1.nc` into package data for release |
| `run_pull_gmstmon.slurm` | PIK | Slurm wrapper for the pull script |

Path manifest: **`src/tipmip_gwl/data/tas_chunks.tsv`** — edit when Levante paths move.

Full documentation: **`docs/gmstmon_pipeline.md`**.
