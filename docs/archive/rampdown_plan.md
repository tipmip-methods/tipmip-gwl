# Ramp-down inclusion plan (Plan B)

Minimal ramp-down support in the **same GMD paper** as ramp-up: same three-step
method, decreasing monotone axis, one new figure, hysteresis caveat. Zero-emission
hold stays deferred (forward relabel only).

**Target:** July/Aug 2026 submission · **Status:** in progress

---

## Progress overview

| Track | Status |
|-------|--------|
| Data staging | ✅ complete (8 models, both dn legs + mlotst) |
| Code / API | ✅ done |
| Mapping products | ✅ 8× dn2c + 8× dn4c in `mapping/` (24 bundled) |
| Paper figures | ✅ hysteresis generated |
| Paper text | ⬜ not started |
| Docs / package | ✅ ramp-down bundled; ZE moved to `exploratory/zehold/` |

---

## 1. Data staging

Destination root: `~/Desktop/tipmip/`

- [x] **0. Sanity check** — `tas/esm-up2p0-gwl2p0-50y-dn2p0/` all 8 Tier‑1 models
- [x] **1. `tas` / `esm-up2p0-gwl4p0-50y-dn2p0`** — all 8 models
- [x] **2. `mlotst` / `esm-up2p0-gwl2p0-50y-dn2p0`** — all 8 models
- [x] **3. `mlotst` / `esm-up2p0-gwl4p0-50y-dn2p0`**
- [x] UKESM metadata fixed

**Models (8):** ACCESS-ESM1-5, EC-Earth3-ESM-1, GFDL-ESM2M, GISS-E2-1-G-CC2,
IPSL-CM6-ESMCO2, MIROC-ES2L, NorESM2-LM, UKESM1-2-LL

---

## 2. Code / API

- [x] **`load_mapping` / `list_models`** — `leg=` aliases (`ramp-up`, `ramp-down-2c`, `ramp-down-4c`)
- [x] **`resample_to_gwl`** — uses mapping `gwl` coordinate by default
- [x] **Tests** — leg resolution, negative-GWL grid, dn4 grid auto-selection
- [x] **Cleanup** — removed `examples/investigate_rampdown.py`
- [x] **`using_mappings.md`** — ramp-down subsection

```python
from tipmip_gwl import load_mapping, resample_to_gwl

mp_dn = load_mapping("GFDL-ESM2M", leg="ramp-down-2c", mapping_dir="mapping/")
on_gwl = resample_to_gwl(mp_dn, diagnostic)
```

---

## 3. Mapping products

- [x] Ramp-up + ramp-down mappings in `mapping/` and bundled (24 files)
- [x] Build **dn from 2 °C ZE** — 8 models (`gwl2p0` / NorESM `swl2p0`)
- [x] Build **dn from 4 °C ZE** — 8 models (auto grid −1.5…4.5 °C)
- [x] UKESM dn2c rebuilt after metadata fix
- [x] Expected parent-chain warnings only (ZE hold parent, informational)

**Rebuild commands:**

```bash
conda activate toad312
tipmip-gwl-build-rampdown \
  --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
tipmip-gwl-build-rampdown \
  --dn-dir ~/Desktop/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon \
  --picontrol-dir ~/Desktop/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

---

## 4. Paper (GMD draft)

### Figures (generated)

- [x] **Mapping axis:** `paper/figures/mapping_axis_up_down.png` (ramp-up + ramp-down, Methods → **Fig. 1**)
- [x] **Hysteresis:** `paper/figures/hysteresis_mlotst_4c.png` (MIROC, resample_to_gwl, dn4 → **Fig. 5**)

Regenerate:

```bash
python paper/plot_mapping_axis_up_down.py --mapping-dir mapping
python paper/plot_hysteresis_mlotst.py \
  --mlotst-up-dir ~/Desktop/tipmip/mlotst/esm-up2p0 \
  --mlotst-dn-dir ~/Desktop/tipmip/mlotst/esm-up2p0-gwl4p0-50y-dn2p0 \
  --mapping-dir mapping
```

Or full pipeline: `python paper/build_all.py` (includes both dn legs via `--dn-dir` / `--dn4-dir`).

Exploratory calendar-axis trajectory (not for paper): `exploratory/zehold/plot_trajectory.py`.

### Text (remaining)

Manuscript checklist: **`phd/Papers/paper_toad_one/`** (Google Doc) and
**`docs/publication_cleanup.md`** in this repo.

- [ ] **Abstract / intro** — ramp-up **and** ramp-down
- [ ] **Methods (~½ page)** — `direction=decreasing`; grids −1.5…2.5 °C (2 °C dn) and −1.5…4.5 °C (4 °C dn); hysteresis caveat
- [ ] **Discussion** — implemented, not future work; ZE hold deferred

---

## 5. Docs / package

- [ ] `README.md` — ramp-down subsection
- [x] `docs/using_mappings.md`
- [ ] `docs/building_mappings.md` — dn4 grid note
- [ ] `docs/paper_figures.md` — hysteresis + dn4-dir

---

## Review checkpoints

- [x] API diff (`product.py`, `rampdown.py`)
- [x] Built `gwlmap_*_dn*.nc` — 16 ramp-down files, no gwl_max warnings on dn4
- [x] Figure drafts in `paper/figures/`
- [ ] Methods paragraph + Discussion tweak (your pass)

---

## Notes

- _2026-07-22 — Data download complete; UKESM metadata patched._
- _2026-07-22 — Built 8+8 ramp-down mappings; fixed dn4 common grid (extends to 4.5 °C)._
- _2026-07-22 — Generated trajectory + mlotst hysteresis figures._
