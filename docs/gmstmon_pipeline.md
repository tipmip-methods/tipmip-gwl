# GMSAT pipeline: from CMIP `tas` to `gmstmon`

How we prepare **global-mean surface air temperature (GMSAT)** for TIPMIP analysis.
This is the archive preprocessing stage of **Step 1 (anomaly computation)** in
the mapping pipeline (see the package README).

**Tool:** `tipmip-gwl-preprocess` + bundled path list `src/tipmip_gwl/data/tas_chunks.tsv`.

HPC helpers: `scripts/` (see `scripts/README.md`).

---

## What you need on disk

One small file per model per experiment:

```text
<outdir>/tas_<table>_<model>_<exp>_<member>_<grid>_gmstmon.nc
```

Monthly, area-weighted global mean. Example local layout:

```text
~/Desktop/tipmip/tas/esm-up2p0/gmstmon/
~/Desktop/tipmip/tas/esm-piControl/gmstmon/
```

The **annual** GMSAT (days-in-month weighted) is applied automatically on read by
`tipmip_gwl.io.load_gmsat_nc` — not a separate preprocessing step.

---

## Path manifest (`tas_chunks.tsv`)

Chunk paths on Levante are listed in **`src/tipmip_gwl/data/tas_chunks.tsv`** — one
row per time chunk:

```text
model	experiment_id	path
ACCESS-ESM1-5	esm-piControl	/work/cmip6/data/CMIP6/CMIP/CSIRO-ARCCSS/.../tas_....nc
...
```

When Levante paths move, edit this file and re-run preprocess — no inventory scan.

---

## Quick start

```bash
conda activate toad312
pip install -e ".[plot]"
```

### Batch (all models, one experiment)

On **Levante**:

```bash
tipmip-gwl-preprocess \
  --exp esm-piControl \
  --outdir /work/bm1448/analysis/harteg/merged/tas/esm-piControl/gmstmon
```

(`--manifest` defaults to the bundled `tas_chunks.tsv`.)

Or submit `scripts/run_preprocess_levante.slurm`.

Copy to laptop (~1 MB per model):

```bash
rsync -avP user@levante.dkrz.de:.../gmstmon/ ~/Desktop/tipmip/tas/esm-piControl/gmstmon/
```

### One model

```bash
tipmip-gwl-preprocess \
  --exp esm-piControl \
  --models ACCESS-ESM1-5 \
  --outdir ./gmstmon
```

### One-off from explicit paths

```bash
tipmip-gwl-preprocess \
  --chunks /path/to/chunk1.nc /path/to/chunk2.nc \
  --out ~/Desktop/tipmip/tas/esm-piControl/gmstmon/tas_Amon_ACCESS-ESM1-5_esm-piControl_r1i1p1f1_gn_gmstmon.nc
```

### Downstream

```bash
tipmip-gwl-build \
  --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

Diagnostic figure: `python examples/mean_tas_piControl.py`

---

## Two weighting steps

| Step | Where | What |
|------|-------|------|
| Spatial mean | `tipmip-gwl-preprocess` | Area-weighted global mean, **keep monthly** |
| Temporal mean | `load_gmsat_nc` (on read) | Days-in-month weighted **annual** mean |

Do **not** use `cdo yearmean` for the baseline.

---

## Backend

| `--backend` | Behaviour |
|-------------|-----------|
| `auto` (default) | CDO if installed (`mergetime` + `fldmean`), else xarray |
| `cdo` | Matches legacy `merge_var.sh` output exactly |
| `xarray` | Pure Python; cos(lat) if no `areacella` passed |

---

## Legacy

`scripts/legacy/` holds the old CDO merge pipeline and `merge_lists/tas/` for
reference. Superseded by `tipmip-gwl-preprocess`.

Mixed-layer **mlotst** scripts remain in `phd-toad/TIPMIP/analysis/mixed-layer/data/`.

---

## Updating paths

1. Find the new absolute path on Levante.
2. Edit `src/tipmip_gwl/data/tas_chunks.tsv`.
3. Re-run `tipmip-gwl-preprocess` for that experiment.

Verify:

```bash
python -c "
from tipmip_gwl.io import load_gmsat_nc
y, t = load_gmsat_nc('path/to/tas_..._gmstmon.nc')
print(int(y.min()), int(y.max()), len(y), round(float(t.mean()), 3))
"
```
