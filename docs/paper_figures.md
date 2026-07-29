# Reproducing paper figures and tables

This guide is for **maintainers and reviewers** who want to rebuild the figures
and tables in the GMD paper from staged TIPMIP data. It is not required for
downstream users who only apply `resample_to_gwl` / `relabel_to_gwl` to their
own diagnostics — see [using_mappings.md](using_mappings.md).

Publication checklist: [publication_cleanup.md](publication_cleanup.md).

## One-command build

From the repository root, with gmstmon and mlotst data staged locally:

```bash
conda activate toad312
pip install -e ".[paper]"

python paper/build_all.py \
  --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon
```

This orchestrator:

1. Rebuilds `mapping/` ramp-up and ramp-down products (when those directories
   are staged)
2. Runs each script under `paper/` in sequence
3. Writes figures to `paper/figures/` and tables to `paper/tables/`

Steps 0b/0c and 8–10 are skipped when ramp-down gmstmon is not staged.

## Step index (`build_all.py`)

| Step | Script | Output |
|------|--------|--------|
| 0 | `tipmip_gwl.build.write_products` | `mapping/gwlmap_*_esm-up2p0_v1.nc` |
| 0b | ramp-down 2 °C builder | `mapping/gwlmap_*_gwl2p0-50y-dn2p0_v1.nc` |
| 0c | ramp-down 4 °C builder | `mapping/gwlmap_*_gwl4p0-50y-dn2p0_v1.nc` |
| 1 | `paper/figures_1_2.py` | `figures/picontrol_baseline.png` |
| 2 | `paper/baseline_sensitivity.py` | `tables/baseline_sensitivity.csv` |
| 3 | `paper/window_sensitivity.py` | `tables/window_sensitivity.csv` |
| 4 | `paper/mean_tas_piControl.py` | `figures/baseline_reference_comparison.png` |
| 5 | `paper/diagnostic_remap_demo.py` | `figures/diagnostic_remap_demo.png` |
| 6 | `paper/diagnostic_remap_binned_demo.py` | `figures/diagnostic_remap_binned_demo.png` |
| 7 | `paper/table1.py` | `tables/table1.csv` |
| 7b | `paper/table_mono_max.py` | `tables/table_mono_max.csv` |
| 8 | `paper/plot_mapping_axis_up_down.py` | `figures/mapping_axis_up_down.png` |
| 9 | `paper/plot_hysteresis_mlotst.py` | **`figures/hysteresis_mlotst_4c.png` (Fig. 5 — global MLD)** |
| 10 | `paper/plot_hysteresis_mlotst_spg.py` | `figures/hysteresis_mlotst_spg_4c.png` (SPG regional; supplementary) |

Each script is also runnable standalone — see its module docstring for arguments.

Exploratory zero-emission-hold QA (not part of the paper build):
`exploratory/zehold/plot_trajectory.py`.

GWL axis spacing and other non-paper figures:
`phd-toad/TIPMIP/analysis/tipmip-gwl-explorations/`.

## Data prerequisites

| Data | Typical path | Used for |
|------|--------------|----------|
| Ramp-up gmstmon | `tas/esm-up2p0/gmstmon/` | mapping build, most figures |
| piControl gmstmon | `tas/esm-piControl/gmstmon/` | baseline, mapping build |
| Mixed-layer depth (up) | `mlotst/esm-up2p0/` | diagnostic remap demos |
| Ramp-down gmstmon (2 °C) | `tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/` | mapping 0b |
| Ramp-down gmstmon (4 °C) | `tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon/` | mapping 0c, hysteresis |
| Mixed-layer depth (dn 4 °C) | `mlotst/esm-up2p0-gwl4p0-50y-dn2p0/` | hysteresis figures (steps 9–10) |

Preprocess tas with `python scripts/build_gmstmon.py` — see [gmstmon_pipeline.md](gmstmon_pipeline.md).
Mapping build detail: [building_mappings.md](building_mappings.md).

## Relationship to the library

Paper scripts demonstrate the same APIs users call in production:

- `resample_to_gwl` and `relabel_to_gwl` in the diagnostic remap figures
- `tipmip_gwl.build.build_mapping_dataset` / `write_products` when regenerating mappings

Bundled mappings under `src/tipmip_gwl/data/mappings/` are the published
snapshot; `build_all.py` rebuilds into `mapping/` for figure consistency with
the staged tas on your machine.

## Tutorial (lighter weight)

Generic resampling walkthrough without full TIPMIP staging:
[examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).
