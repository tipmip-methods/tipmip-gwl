# GMD paper todo — ramp-down + figure integration

Checklist for updating the TIPMIP temp-axis draft (`Paper draft_ TIPMIP temp-axis.pdf`)
now that ramp-down mappings and two new Methods figures exist.

**Target submission:** July/Aug 2026  
**Draft location:** Google Docs / export PDF (not yet in repo)  
**Repo figures:** `paper/figures/`

---

## Progress overview


| Track                           | Status                                |
| ------------------------------- | ------------------------------------- |
| Figures generated               | ✅                                     |
| Figure captions (draft)         | 🟡 Fig. 1 drafted; Fig. 5 draft below |
| Abstract                        | ⬜                                     |
| Introduction                    | ⬜                                     |
| Methods (ramp-down)             | ⬜                                     |
| Sect. 3 data product            | ⬜                                     |
| Discussion                      | ⬜                                     |
| Figure renumbering / cross-refs | ⬜                                     |
| LaTeX / final manuscript        | ⬜                                     |


---



## Figure plan (renumbering)


| New #      | File                                | Replaces / role                      | Section                  |
| ---------- | ----------------------------------- | ------------------------------------ | ------------------------ |
| **Fig. 1** | `mapping_axis_up_down.png`          | **Replaces** old ramp-up-only Fig. 1 | Intro + Methods (Step 2) |
| Fig. 2     | `picontrol_baseline.png`            | unchanged                            | Step 1                   |
| Fig. 3     | `diagnostic_remap_demo.png`         | unchanged (ramp-up relabel)          | Step 3                   |
| Fig. 4     | `diagnostic_remap_binned_demo.png`  | unchanged (resample)                 | Step 3                   |
| **Fig. 5** | `hysteresis_mlotst_4c.png`          | **New** — path dependence example    | **New Sect. 2.2**        |
| Fig. 6     | `baseline_reference_comparison.png` | old Fig. 5                           | Sect. 2.1 Robustness     |


Regenerate:

```bash
conda activate toad312
cd tipmip-gwl
python paper/plot_mapping_axis_up_down.py --mapping-dir mapping
python paper/plot_hysteresis_mlotst.py \
  --mlotst-up-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \
  --mlotst-dn-dir ~/Desktop/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0 \
  --mapping-dir mapping
```

---



## Captions



### Fig. 1 — `mapping_axis_up_down.png` (drafted)

- [x] Draft medium-length caption (see chat / paste into manuscript)
- [x] Paste into Google Doc; update all in-text “Fig. 1” references to two-panel description
- [x] Confirm panel labels (a)/(b) match exported PNG



### Fig. 5 — `hysteresis_mlotst_4c.png` (draft)

- [x] Paste caption:

> **Figure 5.** Path dependence after resampling onto the common GWL grid. Global-mean annual-maximum mixed-layer depth for MIROC-ES2L, resampled with `resample_to_gwl` onto the shared 0.02 °C grid (0–4 °C) using the ramp-up mapping (thick line) and the ramp-down-from-4 °C mapping (thin line). Lower panel: difference down minus up at each grid point where both legs are defined. The offset at fixed GWL illustrates that the same warming level on different protocol legs need not correspond to the same Earth-system state; MIROC-ES2L shows the largest offset among the eight models for this diagnostic. Only the temperature axis is smoothed (Sect. 2); the diagnostic is not.

- [x] Soften “largest among eight” if not verified in final pass

---



## Abstract

- [x] **Remove** closing sentence: *“We restrict attention to the ramp-up leg … left for future work.”*
- [x] **Add** (~2 sentences):
  - Method covers **ramp-up and ramp-down** (after 50-year zero-emission hold at 2 and 4 °C)
  - Decreasing monotone axis; **24 bundled mapping files** (8 models × 3 legs)
  - **Caveat:** equal GWL on different legs ≠ equal state (path dependence)
- [x] Keep existing robustness + data-product sentences

---



## Introduction

- [x] **Para 1:** Update Fig. 1 description — two panels (ramp-up + ramp-down), not ramp-up only
- [x] **Final paragraph:** **Delete** “restrict to ramp-up / future work” block
- [x] **Replace** with: ramp-down implemented; mapping products for both Tier-1 dn branches; Fig. 5 illustrates path dependence; **ZE-hold leg still deferred**
- [x] Optional: one sentence early that TIPMIP Phase 1 includes ramp-down for reversibility/hysteresis

---



## Methods — Sect. 2



### Step 1 (anomaly)

- [ ] Note ramp-down uses GMSAT from dn experiments; **same piControl baseline** as ramp-up (Fig. 2)



### Step 2 (smoothing & monotonicity)

- [ ] Ramp-up: non-decreasing PAVA (existing)
- [ ] Ramp-down: **non-increasing** PAVA on cooling branch
- [ ] Point to Fig. 1(a) vs 1(b) for thick lines



### Step 3 (inversion & resampling)

- [ ] Each leg has its **own mapping file** (`leg=` in `tipmip_gwl`)
- [ ] Same two forms: `relabel_to_gwl` vs `resample_to_gwl`
- [ ] **Hysteresis caveat:** overlapping GWL on up vs dn does not imply comparable state
- [ ] Ramp-down GWL grids: −1.5…2.5 °C (dn from 2 °C), −1.5…4.5 °C (dn from 4 °C)



### New Sect. 2.2 — Ramp-down mapping and path dependence (~½ page)

- [ ] Protocol: 50-year zero-emission hold at 2 or 4 °C → ramp-down at ~2 °C century⁻¹
- [ ] Same three steps; `direction=decreasing`; separate product per branch
- [ ] Reference Fig. 1(b) for monotone axes (both branches overlaid)
- [ ] Reference **Fig. 5** for `resample_to_gwl` + Δ(down − up) on 0.02 °C grid
- [ ] Note ramp-up may not reach 0 °C on axis (starts ~0.1–0.2 °C); dn leg revisits lower GWL
- [ ] Explicit: figure is **illustrative workflow**, not mlotst science / tipping claim



### Sect. 2.1 Robustness

- [ ] Add one line: sensitivity analysis shown is for **ramp-up**; ramp-down uses identical Step 1–2 choices
- [ ] Renumber to **2.3** if 2.2 inserted before it (optional)
- [ ] Update Fig. 5 → **Fig. 6** in robustness text

---



## Sect. 3 — Code and data product

- [ ] Change “once per model” → **once per model per leg**
- [ ] **24 files:** 8 ramp-up + 8 ramp-down-2c + 8 ramp-down-4c (bundled in package)
- [ ] Document `load_mapping(..., leg="ramp-down-2c")` / `leg="ramp-down-4c"`
- [ ] Mention `hysteresis_note` attribute on dn products (if kept in NetCDF attrs)
- [ ] Regeneration: `build_all.py`, `tipmip-gwl-build-rampdown`

---



## Discussion (Sect. 4)

- [ ] **Rewrite opening paragraph** — remove “covers ramp-up only / future work”
- [ ] State ramp-down **implemented and bundled**; same pipeline, decreasing axis
- [ ] Fig. 5: illustrative path dependence; MIROC + mlotst chosen for clarity, not ensemble claim
- [ ] Apply existing 0.1 °C reporting caveat to cross-leg Δ values
- [ ] **Still deferred:** ZE-hold as own mapped leg; three-leg unified hysteresis diagram

---



## Cross-references & housekeeping

- [ ] Renumber old Fig. 5 (baseline sensitivity) → **Fig. 6** throughout
- [ ] Search draft for “ramp-up only”, “future work”, “restrict attention”
- [ ] Search for “Fig. 1” — ensure two-panel wording where needed
- [ ] Search for “once per model” in data-product section
- [x] Table A2 (mono_max): `paper/table_mono_max.py` → `tables/table_mono_max.csv` (one row per model, one column per leg)
- [ ] Table A1: paste baseline CSV into manuscript (no mono_max columns)
- [ ] Table A2: paste mono_max CSV; one sentence in Sect. 2.2 that this is the leg-specific inversion diagnostic
- [ ] Remove or archive stale `hysteresis_mlotst_2c.png` from manuscript if not cited
- [ ] Optional: delete `paper/figures/rampup_anomaly.png` from manuscript (keep for slides)

---



## Repo docs (supporting, not manuscript)

- [ ] Update `docs/paper_figures.md` — Fig. 1 swap, Fig. 5 hysteresis, dn4 mlotst path
- [ ] ~~Update `docs/rampdown_plan.md`~~ — archived to `docs/archive/rampdown_plan.md`
- [ ] `docs/building_mappings.md` — dn4 grid note (if not done)
- [ ] `README.md` — ramp-down subsection (if not done)

---



## Done (figures & code)

- [x] `mapping_axis_up_down.png` — both dn legs, 0/2/4 °C lines, from 2/4 °C labels, legend lower left
- [x] `hysteresis_mlotst_4c.png` — MIROC only, `resample_to_gwl`, dn4, Δ bar panel
- [x] 24 bundled mappings; API `leg=` aliases; tests passing
- [x] ZE-hold moved to `exploratory/zehold/` (not in paper)

---



## Notes

- *2026-07-22 — Figure plan and caption drafts agreed in Cursor session.*
- *Hysteresis figure: global mean (not SPG cells); dn-from-4 °C for full 0–4 °C overlap.*

