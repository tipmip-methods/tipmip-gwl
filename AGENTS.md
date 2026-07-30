# Agent context: tipmip-gwl

Orientation for coding agents. Human docs: `README.md`, `docs/using_mappings.md`,
`docs/building_mappings.md`, `docs/staged_data.md`.

## Three purposes

| Purpose | Location | Audience |
|---------|----------|----------|
| **User library** | `src/tipmip_gwl/` | Apply bundled mappings via `load_mapping`, `resample_to_gwl`, `relabel_to_gwl` |
| **Paper reproduction** | `paper/` | Regenerate committed figures/tables (`pip install -e ".[paper]"`, staged data) |
| **Mapping pipeline** | `src/tipmip_gwl/build.py`, `scripts/` | Rebuild `gwlmap_*.nc` when new gmstmon is available |

Do not expand the installed package beyond the user API. Preprocessing, plotting, and
HPC helpers belong in `scripts/` or `paper/`.

## User API (exported from `tipmip_gwl`)

```python
from tipmip_gwl import load_mapping, list_models, resample_to_gwl, relabel_to_gwl

mp = load_mapping("GFDL-ESM2M")
mp_dn = load_mapping("GFDL-ESM2M", leg="ramp-down-2c")
```

Maintainer builds: `from tipmip_gwl.build import write_products, write_rampdown_products, ...`

## Package modules

| Module | Role |
|--------|------|
| `ensemble.py` | Included Tier-1 model list (`INCLUDED_MODELS`); strict build/sync gate |
| `mapping.py` | Anomaly → 31-yr smooth + PAVA → invert |
| `baseline.py` | piControl reference, branch year, provenance |
| `io.py` | Read gmstmon; calendar-aware annual mean |
| `product.py` | Load bundled mappings, resample/relabel |
| `build.py` | Build `gwlmap_*.nc` (ramp-up + ramp-down) |

## Bundled data

- `src/tipmip_gwl/data/mappings/gwlmap_*_v1.nc` — 24 files (8 ramp-up + 16 ramp-down)
- After local rebuild: `python scripts/sync_bundled_mappings.py`

## Included ensemble

Canonical Tier-1 model ids: `src/tipmip_gwl/ensemble.py` (`INCLUDED_MODELS`).
Mapping builds, bundle sync, and paper figures use this list exclusively; missing
data for any listed model raises `MissingEnsembleDataError`. Trial models in
staging directories are ignored.

## Staged data (not in repo)

See [docs/staged_data.md](docs/staged_data.md). Mapping rebuild output: `mapping/`
(gitignored except when syncing to bundle).

Site-specific HPC/rsync scripts are **not** in this public repo. Maintainer
operational workflow (Levante build, laptop download, full rebuild): sibling clone
**`tipmip-gwl-maintainer`** (`WORKFLOW.md`, `prepare-gmstmon/`, `rebuild_mappings_and_paper.sh`).
Set `TIPMIP_GWL_MAINTAINER` to that clone path when working with those scripts.

## Commands

```bash
pip install -e ".[paper,test]"
pytest
python scripts/build_gmstmon.py --exp esm-up2p0 --outdir ...
tipmip-gwl-build --leg ramp-up --up2p0-dir ... --picontrol-dir ... --outdir mapping/
python paper/build_all.py
```

## Known data quirks

### UKESM mixed-layer depth (`mlotst`)

- Native `*_annualmax.nc`: land is `mlotst = 0`, not NaN (ORCA grid).
- `area_weighted_global_mean` in `paper/helper_mlotst_remap.py` masks cells with
  `max(mlotst) > 0` before averaging.
- Paper figures use native calendar-time files, not pre-remapped GWL-axis products.

### UKESM / NorESM gmstmon duplicates

- Fixed in `scripts/build_gmstmon.py` dedupe + cleaned `tas_chunks.tsv`.
- No science impact on annual GMSAT or bundled mappings.

### UKESM metadata

- Branch year **2277** via `baseline.KNOWN_BRANCH_YEARS`.
- Patch staged attrs: `scripts/fix_ukesm_branch_attrs.py --apply`.

### NorESM2-LM

- Branch year outside staged piControl span → full piControl mean baseline.

### Relabelled GWL axis is unevenly spaced

- Do not smooth after `relabel_to_gwl`. Use `resample_to_gwl` when a uniform grid is
  needed; avoid resampled series for change-point statistics (see user docs).

### Hysteresis

- Never equate ramp-up and ramp-down at the same GWL for the same model.

## Paper reproduction (`build_all.py`)

Scripts are prefixed by role: `fig_*`, `table_*`, `helper_*`.

| Output | Script |
|--------|--------|
| `figures/fig_mapping_axis_up_down.png` | `fig_mapping_axis_up_down.py` |
| `figures/fig_picontrol_baseline.png` | `fig_picontrol_baseline.py` |
| `figures/fig_baseline_reference_comparison.png` | `fig_baseline_reference_comparison.py` |
| `figures/fig_remap_demo.png` | `fig_remap_demo.py` |
| `figures/fig_remap_binned_demo.png` | `fig_remap_binned_demo.py` |
| `figures/fig_hysteresis_mlotst_dn4c.png` | `fig_hysteresis_mlotst.py` |
| `tables/table_baseline_diagnostics.csv` | `table_baseline_diagnostics.py` (Appendix A1) |
| `tables/table_mono_max.csv` | `table_mono_max.py` (Appendix A2) |
| `tables/table_baseline_sensitivity.csv` | `table_baseline_sensitivity.py` |
| `tables/table_window_sensitivity.csv` | `table_window_sensitivity.py` |

Helpers: `helper_diagnostics.py`, `helper_mlotst_remap.py`, `helper_paper_style.py`,
`helper_plot_diagnostics.py`.

## When editing

- Run `pytest` after changes
- British English in user-facing docs
- Minimize scope — resist feature creep in the library
