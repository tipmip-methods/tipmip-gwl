# Paper figure and table reproduction

Scripts under [`paper/`](../paper/) regenerate the committed PNGs and CSVs that
support the GMD manuscript. This is **purpose 3** of the repository (see
[README](../README.md)): mapping **functions + products** (purpose 1) and the
**mapping build pipeline** (purpose 2) live elsewhere in the tree.

**Data are not shipped.** Reviewers and readers see the committed outputs in
`paper/figures/` and `paper/tables/`. Full regeneration requires TIPMIP diagnostics
on disk (institutional access). The commands below document what would be needed
if staged data were available.

---

## Install

```bash
pip install -e ".[paper]"
```

Requires matplotlib (see [`pyproject.toml`](../pyproject.toml) `[project.optional-dependencies]`).

---

## One-command rebuild

[`paper/build_all.py`](../paper/build_all.py) orchestrates mapping rebuilds (when
gmstmon is staged) and every figure/table script in order:

```bash
python paper/build_all.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/data/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon \
  --sivol-up-dir ~/data/tipmip/sivol/esm-up2p0 \
  --sivol-dn-dir ~/data/tipmip/sivol/esm-up2p0-gwl4p0-50y-dn2p0 \
  --mapping-dir mapping
```

Defaults assume `~/data/tipmip/`; override any path with the matching flag.

**Steps skipped automatically** when data or ramp-down mappings are missing:

| Condition | Skipped outputs |
|-----------|-----------------|
| No `--dn-dir` gmstmon | Ramp-down mapping rebuild; Figs 3 & 5 (mapping axes, hysteresis) |
| No `--dn4-dir` gmstmon | Ramp-down 4 °C mapping rebuild |
| No ramp-down mappings rebuilt | `fig_mapping_axis_up_down`, `fig_hysteresis_mlotst` |
| No mlotst dn4 or sivol dirs | `fig_hysteresis_mlotst` only |

Mapping products are written to `--mapping-dir` (default: bundled [`mapping/`](../mapping/)).
Use a separate directory if you do not want to overwrite committed `gwlmap_*.nc` files.

---

## Staged data layout

Root directory (convention: `~/data/tipmip/`):

```text
~/data/tipmip/
  tas/
    esm-piControl/gmstmon/              # *_gmstmon.nc — all 9 included models
    esm-up2p0/gmstmon/                  # ramp-up GMSAT (mapping + most figures)
    esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/ # ramp-down 2 °C (optional)
    esm-up2p0-gwl4p0-50y-dn2p0/gmstmon/ # ramp-down 4 °C (optional)
  mlotst/
    esm-up2p0/                          # native *_annualmax.nc per model
    esm-up2p0-gwl4p0-50y-dn2p0/         # ramp-down mlotst (Fig. 5 panel a)
  sivol/
    esm-up2p0/                          # sea-ice volume (Fig. 5 panels b–c)
    esm-up2p0-gwl4p0-50y-dn2p0/
```

**Included models:** `src/tipmip_gwl/ensemble.py` (`INCLUDED_MODELS` — nine Tier-1 models).

**Building gmstmon from raw tas** (maintainer/HPC): sibling
[`tipmip-gwl-maintainer`](https://github.com/tipmip-methods/tipmip-gwl-maintainer)
or [building_mappings.md](building_mappings.md). See also [staged_data.md](staged_data.md).

---

## Outputs ↔ scripts ↔ data

Committed artefacts and the scripts that produce them. Paper figure numbers follow
the current manuscript draft (adjust captions if numbering changes).

### Figures

| Manuscript | Output | Script | Staged inputs |
|------------|--------|--------|---------------|
| Fig. 1 (piControl baseline) | `paper/figures/fig_picontrol_baseline.png` | `fig_picontrol_baseline.py` | `esm-up2p0`, `esm-piControl` gmstmon |
| Fig. 2 (baseline comparison) | `paper/figures/fig_baseline_reference_comparison.png` | `fig_baseline_reference_comparison.py` | same |
| Fig. 3 (GWL axes up/down) | `paper/figures/fig_mapping_axis_up_down.png` | `fig_mapping_axis_up_down.py` | `mapping/` (ramp-up + ramp-down products) |
| Fig. 4 (remap demo) | `paper/figures/fig_remap_demo.png` | `fig_remap_demo.py` | `mlotst/esm-up2p0`, `mapping/` |
| Fig. 4 (binned detail) | `paper/figures/fig_remap_binned_demo.png` | `fig_remap_binned_demo.py` | same |
| Fig. 5 (hysteresis) | `paper/figures/fig_hysteresis_mlotst_dn4c.png` | `fig_hysteresis_mlotst.py` | mlotst up+dn4, sivol up+dn4, `mapping/` |

### Tables (Appendix)

| Manuscript | Output | Script | Staged inputs |
|------------|--------|--------|---------------|
| Table A1 | `paper/tables/table_baseline_diagnostics.csv` | `table_baseline_diagnostics.py` | gmstmon up + piControl |
| Table A2 | `paper/tables/table_mono_max.csv` | `table_mono_max.py` | `mapping/`, gmstmon up + piControl |
| — (sensitivity) | `paper/tables/table_baseline_sensitivity.csv` | `table_baseline_sensitivity.py` | gmstmon up + piControl |
| — (window sweep) | `paper/tables/table_window_sensitivity.csv` | `table_window_sensitivity.py` | gmstmon up + piControl |

---

## Run scripts individually

Each script is standalone (see its module docstring). Typical invocations:

```bash
# Baseline diagnostics (Figs 1–2, Tables A1, sensitivity tables)
python paper/fig_picontrol_baseline.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon

python paper/table_baseline_diagnostics.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon

# Remap illustrations (Fig. 4)
python paper/fig_remap_demo.py \
  --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --mapping-dir mapping

# GWL axes (Fig. 3) — uses bundled mappings only
python paper/fig_mapping_axis_up_down.py --mapping-dir mapping

# Hysteresis (Fig. 5)
python paper/fig_hysteresis_mlotst.py \
  --mlotst-up-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --mlotst-dn-dir ~/data/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0 \
  --sivol-up-dir ~/data/tipmip/sivol/esm-up2p0 \
  --sivol-dn-dir ~/data/tipmip/sivol/esm-up2p0-gwl4p0-50y-dn2p0 \
  --mapping-dir mapping
```

Helper modules (`helper_*.py`) are imported by the scripts above; they are not run directly.

---

## What reviewers get without data

| In the repository | Not in the repository |
|-------------------|------------------------|
| All figure PNGs and table CSVs under `paper/` | Raw tas, gmstmon, mlotst, sivol NetCDFs |
| Bundled mapping coordinate products (`mapping/`) | TIPMIP download instructions (institution-specific) |
| Library to apply mappings to user diagnostics | Guaranteed one-click reproduction without staged data |

For applying mappings to custom diagnostics (no paper rebuild), see
[using_mappings.md](using_mappings.md) and [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).
