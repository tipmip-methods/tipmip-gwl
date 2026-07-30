# Agent context: tipmip-gwl

Orientation for coding agents. Human docs: `README.md` and `docs/`.

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
| `mapping.py` | Anomaly → 31-yr smooth + PAVA → invert |
| `baseline.py` | piControl reference, branch year, provenance |
| `io.py` | Read gmstmon; calendar-aware annual mean |
| `product.py` | Load bundled mappings, resample/relabel |
| `build.py` | Build `gwlmap_*.nc` (ramp-up + ramp-down) |

## Bundled data

- `src/tipmip_gwl/data/mappings/gwlmap_*_v1.nc` — 24 files (8 ramp-up + 16 ramp-down)
- After local rebuild: `python scripts/sync_bundled_mappings.py`

## Staged data (not in repo)

```
~/data/tipmip/tas/esm-up2p0/gmstmon/
~/data/tipmip/tas/esm-piControl/gmstmon/
~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/
~/data/tipmip/mlotst/esm-up2p0/          # native *_annualmax.nc
```

Mapping rebuild output: `mapping/` (gitignored except when syncing to bundle).

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
- `area_weighted_global_mean` in `paper/mlotst_remap_helpers.py` masks cells with
  `max(mlotst) > 0` before averaging.
- Paper figures use native calendar-time files, not pre-remapped GWL-axis products.

### UKESM / NorESM gmstmon duplicates

- Fixed in `scripts/build_gmstmon.py` dedupe + cleaned `tas_chunks.tsv`.
- No science impact on annual GMSAT or bundled mappings.

### UKESM metadata

- Branch year **2277** via `baseline.KNOWN_BRANCH_YEARS`.
- Patch staged attrs: `scripts/patch_ukesm_branch_attrs.py --apply`.

### NorESM2-LM

- Branch year outside staged piControl span → full piControl mean baseline.

### Relabelled GWL axis is unevenly spaced

- Do not smooth after `relabel_to_gwl`. Use `resample_to_gwl` when a uniform grid is
  needed; avoid resampled series for change-point statistics (see user docs).

### Hysteresis

- Never equate ramp-up and ramp-down at the same GWL for the same model.

## Paper figures (`build_all.py`)

| Output | Script |
|--------|--------|
| Mapping axes up/down | `plot_mapping_axis_up_down.py` |
| piControl baseline | `figures_1_2.py` |
| mlotst remap demo | `diagnostic_remap_demo.py` |
| Fig. 5 global MLD hysteresis | `plot_hysteresis_mlotst.py` |
| Table A1 / A2 | `table1.py`, `table_mono_max.py` |

## When editing

- Run `pytest` after changes
- British English in user-facing docs
- Minimize scope — resist feature creep in the library
