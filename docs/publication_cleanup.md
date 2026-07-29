# Publication cleanup checklist

GMD submission readiness for **tipmip-gwl** (code + paper reproduction).  
Manuscript prose lives in `phd/Papers/paper_toad_one/` (Google Doc is primary).

**Status legend:** `[x]` done · `[~]` in progress · `[ ]` open

---

## Blockers (before submission)

| | Task | Notes |
|---|------|-------|
| [ ] | **Manuscript finalised** | Abstract through Discussion; figure numbers match committed PNGs |
| [x] | **Figure 5 locked** | Global MLD: `hysteresis_mlotst_4c.png` (`plot_hysteresis_mlotst.py`, MIROC-ES2L, dn-from-4 °C) |
| [x] | **`pyproject.toml` metadata** | `authors`, `license`, `project.urls`, classifiers |
| [x] | **LICENSE file** | BSD-2-Clause in repo root |
| [ ] | **Version tag + archive** | Tag `v0.1.0`, GitHub release; Zenodo DOI when available |
| [ ] | **Full `build_all.py` rebuild** | One clean run on staged data; figures match manuscript |

---

## Repo hygiene

| | Task | Notes |
|---|------|-------|
| [x] | Remove stale `docs/paper_todo.md` | Deleted from `main` |
| [x] | Update `AGENTS.md` | Points to `paper_toad_one`; CESM2 audit in phd-toad |
| [x] | Sync `docs/paper_figures.md` with `build_all.py` | Step index, outputs, data paths |
| [x] | Fix archive doc stale links | `docs/archive/rampdown_plan.md` |
| [x] | Add this checklist | `docs/publication_cleanup.md` |
| [x] | Commit pending doc edits | Fig 5 PNG, LICENSE, `pyproject.toml`, cleanup docs |
| [x] | Reconcile hysteresis script | Fig. 5 = global MLD (`plot_hysteresis_mlotst.py`) |
| [x] | Remove SPG hysteresis artefact | Deleted script, PNG, regional helpers, and `test_mlotst_remap_helpers.py` |

---

## Manuscript / science alignment

| | Task | Notes |
|---|------|-------|
| [ ] | **`relabel` vs `resample` guidance** | Discussion + cite appendix spacing figure |
| [ ] | **Fig. A1 (`gwl_axis_spacing`)** | In phd-toad explorations; cite or copy to SI |
| [x] | **Ramp-down GWL grid prose** | Unified −2…5 °C grid in manuscript + user docs |
| [ ] | **NorESM baseline caveat** | Table A1 / Methods |
| [ ] | **Hysteresis framing** | Fig. 5 uses MIROC-ES2L global-mean mlotst as path-dependence example, not an ensemble claim |

---

## Publication infrastructure

| | Task | Notes |
|---|------|-------|
| [ ] | **Reproducibility env** | `environment.yml` or pinned deps beyond “use toad312” |
| [ ] | **CI (optional)** | GitHub Action: `pytest` on push |
| [ ] | **Bundled mapping provenance** | Spot-check attrs on shipped `.nc` files |
| [ ] | **CMIP / co-author attribution** | Data access statement if required |

---

## Explicitly out of v1 bundle

| Item | Location |
|------|----------|
| CESM2 trial | `phd-toad/TIPMIP/analysis/tipmip-gwl-explorations/cesm2/` |
| ZE-hold exploratory | `exploratory/zehold/` |
| SO / sivol / siconc figures | `phd-toad/.../tipmip-gwl-explorations/` |

---

## Committed paper figures (current)

| File | Script |
|------|--------|
| `paper/figures/mapping_axis_up_down.png` | `plot_mapping_axis_up_down.py` |
| `paper/figures/picontrol_baseline.png` | `figures_1_2.py` |
| `paper/figures/baseline_reference_comparison.png` | `mean_tas_piControl.py` |
| `paper/figures/diagnostic_remap_demo.png` | `diagnostic_remap_demo.py` |
| `paper/figures/diagnostic_remap_binned_demo.png` | `diagnostic_remap_binned_demo.py` |
| **`paper/figures/hysteresis_mlotst_4c.png`** | **`plot_hysteresis_mlotst.py` (Fig. 5 — global MLD)** |

---

## Quick commands

```bash
conda activate toad312
pip install -e ".[paper,test]"
pytest
python paper/build_all.py \
  --up2p0-dir ~/Desktop/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon
```
