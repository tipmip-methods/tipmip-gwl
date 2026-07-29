# Agent context: tipmip-gwl

Quick orientation for coding agents. Human docs live in `README.md` and `docs/`.
Manuscript draft: `phd/Papers/paper_toad_one/` (Google Doc is primary).
Submission checklist: `docs/publication_cleanup.md`.

## What this repo is

GMD paper + installable Python package: **re-index TIPMIP model output from
calendar time onto a global warming level (GWL) axis**. Ships **24 bundled
mapping NetCDFs** (8 ramp-up + 16 ramp-down) as coordinate products — not
remapped fields. Users apply `resample_to_gwl` / `relabel_to_gwl` to their own
annual diagnostics.

**Paper angle:** align Tier-1 models on a common GWL axis; ramp-down legs
included (Plan B); hysteresis caveat (same GWL on up vs down ≠ same state).

## Mental model: three layers

| Layer | Location | Purpose |
|-------|----------|---------|
| **User library** | `src/tipmip_gwl/` | `load_mapping`, `resample_to_gwl`, `relabel_to_gwl` |
| **Maintainer tooling** | `src/tipmip_gwl/build.py`, `scripts/` | Build mappings, gmstmon, sanity tables, sync bundle |
| **Paper reproduction** | `paper/` | Figures/tables; needs staged data + `pip install -e ".[paper]"` |

Do not expand the installed package unless the feature belongs in the **user**
API. Preprocessing, diagnostics, and plotting belong in `scripts/` or `paper/`.

## User API (only these are exported from `tipmip_gwl`)

```python
from tipmip_gwl import load_mapping, list_models, resample_to_gwl, relabel_to_gwl

mp = load_mapping("GFDL-ESM2M")                          # ramp-up default
mp_dn = load_mapping("GFDL-ESM2M", leg="ramp-down-2c")  # or ramp-down-4c
```

Maintainer builds: `from tipmip_gwl.build import build_mapping_dataset, write_products, ...`

## Package modules (`src/tipmip_gwl/`)

| Module | Role |
|--------|------|
| `mapping.py` | Pure algorithm: anomaly → 31-yr smooth + PAVA → invert |
| `baseline.py` | piControl reference, branch year, provenance |
| `io.py` | Read gmstmon; calendar-aware annual mean (`days_in_month`) |
| `product.py` | Load bundled mappings, leg resolution, resample/relabel |
| `build.py` | Build `gwlmap_*.nc` products (ramp-up + ramp-down) |

Shared ramp-up pipeline step: `build.compute_rampup_leg()` (used by build +
`scripts/run_diagnostics.py`).

## Algorithm (paper Steps 1–3)

1. GMSAT anomaly vs piControl baseline (31-yr branch window when branch year known)
2. 31-yr centred running mean + isotonic (PAVA); ramp-down uses **decreasing**
3. Invert to common GWL grid → store `year_of_gwl(gwl)` and `gwl_axis(year)`

## Bundled data

- `src/tipmip_gwl/data/mappings/gwlmap_*_v1.nc` — 24 files, version `v1`
- After local rebuild: `python scripts/sync_bundled_mappings.py`

## Staged data (maintainer / paper; not in repo)

Default laptop layout:

```
~/Desktop/tipmip/tas/esm-up2p0/gmstmon/
~/Desktop/tipmip/tas/esm-piControl/gmstmon/
~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/
~/Desktop/tipmip/mlotst/esm-up2p0/          # native *_annualmax.nc
~/Desktop/tipmip/mapping/                     # optional local rebuild
```

Levante paths: `scripts/data/tas_chunks.tsv` + `scripts/build_gmstmon.py`.

## Common commands

```bash
conda activate toad312
pip install -e ".[paper,test]"

pytest                                    # always use toad312
python scripts/build_gmstmon.py --exp esm-up2p0 --outdir ...
python scripts/run_diagnostics.py --up2p0-dir ... --picontrol-dir ...
tipmip-gwl-build --leg ramp-up --up2p0-dir ... --picontrol-dir ... --outdir mapping/
tipmip-gwl-build --leg ramp-down --dn-dir ... --picontrol-dir ... --outdir mapping/
python paper/build_all.py                 # full paper rebuild (needs staged data)
```

## Known data quirks (do not rediscover)

### UKESM mixed-layer depth (`mlotst`)

- **Native** `*_annualmax.nc`: land is **`mlotst = 0`**, not NaN (ORCA grid).
- **`area_weighted_global_mean`** in `paper/mlotst_remap_helpers.py` masks cells
  with `max(mlotst) > 0` before averaging.
- **`*_annualmax_toad.nc`**: land already NaN; different cell count/processing —
  do not confuse with native files used in paper mlotst figures.

### UKESM / NorESM gmstmon duplicates

- Ramp-up gmstmon had duplicate monthly timesteps (overlapping tas chunks + CDO
  merge). Fixed in `scripts/build_gmstmon.py` dedupe + cleaned `tas_chunks.tsv`.
- **No science impact** on annual GMSAT or bundled mappings (verified bit-identical).

### UKESM metadata

- Branch year **2277** enforced via `baseline.KNOWN_BRANCH_YEARS`.
- Raw attrs may be wrong; patch with `scripts/patch_ukesm_branch_attrs.py --apply`.
- UKESM uses **360-day calendar**; annual mean uses `days_in_month` in `io.py`.

### NorESM2-LM

- Branch year outside staged piControl span → falls back to full piControl mean
  (`ref_full == ref_window`, |Δref| = 0 in Table A1).

### Relabelled GWL axis is unevenly spaced (do not "fix" it)

- `gwl_axis` is a 31-yr running mean, so its annual increment is a difference of
 two individual annual GMSAT values: 26–50 % year-to-year jitter about a mean
 rate of ~0.019 °C/yr, local rates from ~0 to 2.6× the model median.
- Curves plotted against `relabel_to_gwl` output therefore look kinked even for
 an input that is **exactly linear in time**. This is the coordinate, not the
 data: `relabel_to_gwl` returns values bit-identical to the input.
- PAVA plateaus are **not** the cause — tied years are 0–2.2 % of the record and
 the longest run is 1–2 yr. Do not smooth after `relabel_to_gwl` (uneven axis).
- `resample_to_gwl` does interpolate, and its sampling ratio varies: one 0.02 °C
 step represents 0.7–4.8 simulated years (p05–p95 across models; median ≈ 1,
 since the step is one year at the nominal 2 °C/century rate). It **interpolates
 where warming is fast** (17–56 % of steps span < 1 yr, inflating effective
 degrees of freedom → over-detection) and **thins where warming is slow**
 (information loss). Direction is easy to get backwards; years per step
 = 0.02 / rate. Also amplifies RMS second difference 1.6–7.7×.
- Avoid resampled series for change-point statistics whose null depends on
 sample count or autocorrelation. Detect on annual time, then relabel the
 detected year; for GWL-unit windows, use the `relabel_to_gwl` coordinate
 directly. Smoothing after `resample_to_gwl` is legitimate (grid is uniform).
- GWL axis spacing figure and related QA: `phd-toad/TIPMIP/analysis/tipmip-gwl-explorations/`.

### Hysteresis

- **Never** equate ramp-up and ramp-down at the same GWL for the same model.
- Mapping products carry `hysteresis_note` / `leg` attrs.

## What usually does **not** need rebuilding

- Tables A1/A2 or figures after gmstmon dedupe or UKESM metadata-only fixes
  (values unchanged).
- Full mapping rebuild unless gmstmon or baseline logic actually changed.

## Paper figures (current)

| Output | Script |
|--------|--------|
| Mapping axes up/down | `paper/plot_mapping_axis_up_down.py` |
| piControl baseline | `paper/figures_1_2.py` |
| mlotst remap demo | `paper/diagnostic_remap_demo.py` |
| **Fig. 5 — global MLD hysteresis (4 °C leg)** | `paper/plot_hysteresis_mlotst.py` → `hysteresis_mlotst_4c.png` |
| Table A1 / A2 | `paper/table1.py`, `paper/table_mono_max.py` |

Orchestrator: `paper/build_all.py`. Style: `paper/paper_style.py`.

## Related work outside this repo

- **Mixed-layer clustering / TOAD:** `phd-toad/TIPMIP/analysis/mixed-layer/`
  (separate pipeline; produces `*_annualmax_toad.nc` on GWL axis).
- **Paper-adjacent GWL explorations:** `phd-toad/TIPMIP/analysis/tipmip-gwl-explorations/`
  (GWL axis spacing, SO/sivol/siconc figures — not in `build_all.py`).
- **CESM2 trial audit (not bundled):** `phd-toad/TIPMIP/analysis/tipmip-gwl-explorations/cesm2/`
  (ramp-down QA, figures, tables; mappings stay local in `mapping_cesm2/` if rebuilt).
- **Manuscript LaTeX:** `phd/Papers/paper_toad_one/` (Google Doc is primary draft).

## Refactor history (2026-07)

Package was deliberately **leaned**: `preprocess`, `diagnostics`, `plotting`,
and `rampdown` removed from the install surface; merged into `build.py`,
`scripts/`, and `paper/`. Prefer small diffs; avoid re-expanding `__init__.py`.

## When editing

- **Tests:** `conda activate toad312 && pytest`
- **British English** in manuscript-facing text (see paper_toad_one `.cursorrules`)
- **Do not commit** unless the user asks
- **Minimize scope** — this is a simple method; resist feature creep in the library
