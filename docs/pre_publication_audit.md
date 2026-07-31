# Pre-publication audit (tipmip-gwl)

Structured audit before public GitHub + Zenodo release and GMD submission.
Work **one part per chat session** — copy the **Prompt** block verbatim for each part.

**Repos in scope:** `tipmip-gwl`, `tipmip-gwl-mappings` (private), `tipmip-gwl-maintainer` (private).

**Paper draft (source of truth for GMD claims):**
[`Paper draft_ TIPMIP temp-axis.pdf`](../Paper%20draft_%20TIPMIP%20temp-axis.pdf)
(GMD, “Aligning TIPMIP Models on a Common Global-Warming-Level Axis”).

Every audit part should flag **paper ↔ code ↔ figures/tables** mismatches as
`PAPER-DRIFT` in the finding text.

**Finding severity:** `CRITICAL` · `HIGH` · `MEDIUM` · `nit`

**Default rule:** report only (do not fix) unless the prompt says otherwise.

---

## Progress

| Part | Topic | Status | Date | Notes |
|------|--------|--------|------|-------|
| 1 | Mapping algorithm & science | ✅ | 2026-07-30 | FAIL — 2 CRITICAL, 4 HIGH (Opus) |
| 2 | User API & edge cases | ✅ | 2026-07-30 | FAIL — 1 CRITICAL, 4 HIGH (Opus) |
| 3 | Ensemble gating & data layout | ✅ | 2026-07-30 | PASS w/ findings — 1 HIGH (Composer) |
| 4 | Mappings repo split & install | ✅ | 2026-07-30 | FAIL — 1 CRITICAL, 3 HIGH (Composer) |
| 5 | Paper reproduction | ✅ | 2026-07-30 | FAIL captions — 3 HIGH, 5 MEDIUM (Opus) |
| 6 | gmstmon pipeline | ✅ | 2026-07-30 | FAIL — 2 CRITICAL, 5 HIGH (Opus) |
| 7 | Tests & CI gaps | ✅ | 2026-07-30 | FAIL — 6 CRIT missing tests, no CI (Composer) |
| 8 | Publication surface | ✅ | 2026-07-30 | FAIL — 1 CRITICAL notebook (Composer) |
| 10 | Paper ↔ implementation traceability | ✅ | 2026-07-30 | 27 OK, 14 DRIFT, 2 UNVERIFIED (Opus) |
| — | Consolidated release checklist | ✅ | 2026-07-30 | 41 deduped items; notebook RESOLVED |

Mark **Status** with ✅ when done. Paste findings into [Findings log](#findings-log) below.

---

## Paper claims checklist (verified in Part 10)

Part 10 walked every item below (traceability table in [Part 10](#part-10-paper-traceability)).
**No second audit pass needed** — update ticks here when you fix DRIFT items.

Legend: `[x]` OK · `[ ]` DRIFT or open · `[ ]` UNVERIFIED (pre-submission)

### Method (Sect. 2)

- [x] **Three steps:** (1) piControl baseline anomaly, (2) 31-yr running mean + PAVA, (3) relabel vs resample — `map_model` (M1)
- [x] **GMSAT:** area-weighted global mean of `tas`; **days-in-month-weighted** annual mean — `io.load_gmsat_nc` (M2)
- [ ] **Baseline:** 31-yr window centred on ramp-up branch year; **trailing** for ACCESS & EC-Earth; **full mean** for NorESM; **same baseline** all legs — **DRIFT:** GISS window is 21 yr not 31; rules otherwise OK (M3–M6, P10-5)
- [ ] **UKESM1-2-LL:** branch year **2277** — **DRIFT:** value correct in v1 but hand-patched in staged attrs; no code fallback; caption says "decoded" (M7, P10-5)
- [ ] **Smoothing:** 31-yr **centred** running mean on anomaly only; diagnostics **not** smoothed — **DRIFT:** window shrinks at edges, not centred; diagnostics OK (M8–M9, P10-1)
- [x] **PAVA:** non-decreasing ramp-up; non-increasing ramp-down; `mono_max` / Table A2 (M10–M11)
- [x] **Inversion:** epsilon nudge; **PCHIP** t(GWL); NaN beyond range (M12–M14)
- [ ] **Resample grid:** 0–4 °C / −2–5 °C @ 0.02 °C; 201 / 351 pts; shared 0–4 aligned — **DRIFT:** stored grids OK (M15–M17); ramp-up **product range** truncated at 4 °C for 7/8 models, undocumented (M19, P10-2)
- [ ] **Relabel:** forward GWL(t); sub-annual via linear interp in calendar time — **DRIFT:** works on decimal-year only; `datetime64` → silent empty array (M20, P10-4)
- [x] **Resample:** linear time interp at fractional year; no extrapolation (M22–M23)
- [x] **Hysteresis caveat:** up ≠ down at same GWL; zero-emission hold not mapped (M27–M28)

### Ensemble & product (Sect. 2–3)

- [x] **Eight** Tier-1 models = `INCLUDED_MODELS`; no CESM2 in products (E1)
- [x] **24** mapping files, version **v1** (E2)
- [x] Product = coordinate transform only; no pre-remapped fields (E3)
- [ ] **Provenance** on output — **DRIFT:** `tracking_id`s + versions present (E4); Sect. 3 overstates Table A1 attrs on file (`ref_full`, `|Δref|` missing) (E6, P10-8)
- [x] **`leg` API:** `ramp-down-2c`, `ramp-down-4c` match paper (M24)

### Robustness (Sect. 2.3, Appendix A)

- [ ] **Table A1** CSV vs printed table — **DRIFT:** numeric rows match (R1); NorESM CSV columns misleading vs printed "–" (R2, P10-13)
- [x] **Table A2** matches `table_mono_max.csv` and products (R3)
- [x] Baseline sensitivity: `table_baseline_sensitivity.csv`, `fig_baseline_reference_comparison.png` (R4–R5)
- [ ] **Window sensitivity** 21/31/41 yr — **DRIFT (nit):** paper says 3.3 yr, table max 3.393 → 3.4 (R6)

### Figures ↔ scripts (Part 5 rebuild: all byte-identical)

| Paper | Status | Note |
|-------|--------|------|
| Fig. 1 | DRIFT | Cropped 220 yr / 4.5 °C unstated (F1) |
| Fig. 2 | OK | Baseline cases match caption |
| Fig. 3 | DRIFT | Relabel correct; caption wrong (4 °C clip) (F3, P10-7) |
| Fig. 4 | DRIFT | Resample demo OK; caption colours wrong (F4) |
| Fig. 5 | OK | Hysteresis + grid alignment |
| Fig. 6 | OK | Seven-of-eight baseline comparison |

Scripts: `fig_mapping_axis_up_down.py` … `fig_baseline_reference_comparison.py` (unchanged mapping in original table).

### Data & code availability (Sect. 3, end)

- [ ] Public **code** GitHub + Zenodo DOI — **UNVERIFIED:** placeholders only (D1)
- [ ] **Mappings** restricted Zenodo + Levante — **DRIFT:** repo split OK; paper Sect. 3 says "on github"; Levante path ≠ README (D3–D4, P10-3, P10-6)
- [x] "Single driver script" → `paper/build_all.py` reproduces all figures/tables (D5)
- [ ] **CDO fldmean** for GMSAT — **DRIFT:** v1 inputs all CDO-built; code allows silent xarray fallback (D6)

### Known paper–repo deltas (Part 10)

- [x] **CESM2** on cover only — absent from code, products, analysis (K1)
- [ ] **Levante path** — still mismatched paper vs README (K2)
- [ ] **Internal cover** "problematic models" notes — outdated (UKESM/NorESM resolved in v1) (K3)

---

## How to run a part

1. Open a **new chat** (or clear context) for each part — avoids skim.
2. Copy the part's **Prompt** block.
3. Ask: **Report only. Numbered findings with file:line and repro steps. Tag PAPER-DRIFT where relevant.**
4. Record results in [Findings log](#findings-log).
5. Tick the progress table and paper checklist items verified.

Optional after Parts 6–1–2: run Bugbot on the diff since last public push.

**Recommended order:** 6 → 1 → 2 → 5 → 10 → 3 → 4 → 7 → 8 → consolidated checklist.

Run **Part 6 before Part 1**: Table A1 baseline/drift and everything downstream in the
mapping algorithm depends on GMSAT/gmstmon being correct first; a Part 6 finding would
otherwise force re-verification of Part 1.

---

## Part 1 — Mapping algorithm & science correctness

**Prerequisite:** Part 6 (GMSAT/gmstmon inputs).

**Scope:** `src/tipmip_gwl/mapping.py`, `baseline.py`, `build.py`, `io.py`

**Paper:** Sect. 2.1 (Steps 1–2), 2.2 (ramp-down), 2.3 (robustness); Appendix A.

**Read for:** piControl baseline (centred vs trailing vs full-mean), branch-year edge cases
(NorESM, UKESM, ACCESS, EC-Earth), 31-yr smooth + PAVA + PCHIP inversion, ramp-up vs ramp-down
legs, days-in-month annual GMSAT, flat-segment epsilon, grid sizes 201/351.

**Run:**

```bash
conda activate toad312
cd tipmip-gwl
pytest tests/test_mapping.py tests/test_baseline.py tests/test_product.py tests/test_rampdown.py -v
```

**Deliverable:** Any case where published v1 mappings could be **scientifically wrong** for an
included model, or where code **contradicts Sect. 2** of the paper.

### Prompt

```
Audit Part 1 — mapping algorithm & science correctness (tipmip-gwl).

Read fully: src/tipmip_gwl/mapping.py, baseline.py, build.py, io.py.
Read paper: Paper draft_ TIPMIP temp-axis.pdf Sect. 2 and Appendix A.
Run: pytest tests/test_mapping.py tests/test_baseline.py tests/test_product.py tests/test_rampdown.py -v

Verify: baseline rules (centred/trailing/full), 31-yr smooth, PAVA, PCHIP inversion t(GWL),
grid 0–4 / −2–5 at 0.02 °C, mono_max, UKESM 2277, NorESM/ACCESS/EC-Earth edge cases.
Cross-check Table A1/A2 CSVs against mapping products if tipmip-gwl-mappings is present.

Report only. CRITICAL / HIGH / MEDIUM / nit; tag PAPER-DRIFT where paper ≠ code.
Do not fix yet.
```

- [x] Part 1 complete

---

## Part 2 — User API & edge cases

**Scope:** `src/tipmip_gwl/product.py`, `__init__.py`, `docs/using_mappings.md`, README example

**Paper:** Step 3 (relabel vs resample), Sect. 2.2 (leg argument), Discussion (0.1 °C reporting vs 0.02 °C grid).

**Read for:** `load_mapping`, `list_models`, `resample_to_gwl`, `relabel_to_gwl`; missing
`tipmip-gwl-mappings`; partial legs; NaN / no extrapolation; spatial vs scalar diagnostics;
wrong `year_dim`; hysteresis (up vs down at same GWL).

**Run:**

```bash
pytest tests/test_product.py -v
# Requires sibling tipmip-gwl-mappings for bundled tests
```

**Deliverable:** User-facing bugs, misleading errors, or API behaviour that **contradicts Step 3** in the paper.

### Prompt

```
Audit Part 2 — user API & edge cases (tipmip-gwl).

Read: product.py, __init__.py, docs/using_mappings.md, README.md.
Read paper Step 3 (relabel vs resample, sub-annual, no extrapolation, hysteresis caveat).
Run: pytest tests/test_product.py -v

Verify relabel_to_gwl matches forward GWL(t); resample_to_gwl matches inverse t(GWL) + linear time interp;
leg names ramp-down-2c / ramp-down-4c; behaviour for spatial diagnostics.

Report only. Tag PAPER-DRIFT where paper ≠ code. Do not fix yet.
```

- [x] Part 2 complete

---

## Part 3 — Ensemble gating & data layout

**Scope:** `src/tipmip_gwl/ensemble.py`, `build.py`, maintainer `check_staged_gmstmon.py`

**Paper:** “eight available TIPMIP ESM Tier 1 models”, “24 files”, model list in Tables A1/A2.

**Read for:** `INCLUDED_MODELS` matches paper eight; `REQUIRED_GMSTMON_EXPERIMENTS`; builds fail
loudly; no CESM2/trial models in products.

**Run:**

```bash
pytest tests/test_ensemble.py -v
```

### Prompt

```
Audit Part 3 — ensemble gating & data layout.

Read: ensemble.py, build.py, paper/helper_paper_style.py, check_staged_gmstmon.py.
Read paper: abstract + Tables A1/A2 model list.
Run: pytest tests/test_ensemble.py -v

Confirm eight models and 24 v1 files match paper; no trial models in tipmip-gwl-mappings.

Report only. Tag PAPER-DRIFT. Do not fix yet.
```

- [x] Part 3 complete

---

## Part 4 — Mappings repo split & install path

**Scope:** `product.py`, README, `docs/staged_data.md`, paper Sect. 3 & data availability

**Paper:** GitHub + restricted Zenodo mappings; Levante path; coordinate product only.

### Prompt

```
Audit Part 4 — mappings repo split & install vs paper data availability.

Read: product.py, README.md, docs/staged_data.md, paper Sect. 3 and end matter.
Verify public repo has no gwlmap_*.nc; paper Levante/Zenodo/GitHub wording matches current split.

Report only. Tag PAPER-DRIFT. Do not fix yet.
```

- [x] Part 4 complete

---

## Part 5 — Paper reproduction

**Scope:** `paper/build_all.py`, all `fig_*` / `table_*` / `helper_*`

**Paper:** Figs 1–6, Tables A1–A2, sensitivity tables; captions (mlotst masking, cos(lat) global mean).

**Run (if staged data available):**

```bash
pip install -e ".[paper]"
python paper/build_all.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/data/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon
```

Compare committed `paper/figures/` and `paper/tables/` to paper draft figures/tables.

### Prompt

```
Audit Part 5 — paper reproduction vs GMD draft.

Read build_all.py and every fig_* / table_* / helper_* script.
Read paper draft PDF figures and tables (Figs 1–6, Tables A1–A2).
Run build_all.py if staged data exists; diff committed PNG/CSV to what paper describes.

Verify captions: relabel vs resample in Fig 3/4, hysteresis in Fig 5, baseline Fig 6, mlotst cos(lat) mask.

Report only. Tag PAPER-DRIFT for caption/code/figure mismatches. Do not fix yet.
```

- [x] Part 5 complete

---

## Part 6 — gmstmon pipeline

**Start here** (recommended first audit part — upstream of Part 1 / Table A1).

**Scope:** `scripts/build_gmstmon.py`, `fix_ukesm_branch_attrs.py`, `io.py`

**Paper:** Sect. 2 opening (“CDO fldmean”, days-in-month annual mean); UKESM branch metadata.

### Prompt

```
Audit Part 6 — gmstmon pipeline vs paper GMSAT definition.

Read: build_gmstmon.py, fix_ukesm_branch_attrs.py, io.load_gmsat_nc.
Read paper: GMSAT / tas / fldmean / days-in-month paragraphs in Sect. 2.
Run: pytest tests/test_build_gmstmon.py tests/test_io.py -v

Report whether paper wording (CDO fldmean) matches actual preprocessing path.

Report only. Tag PAPER-DRIFT. Do not fix yet.
```

- [x] Part 6 complete

---

## Part 7 — Tests & CI gaps

**Scope:** `tests/`, paper claims without test coverage

### Prompt

```
Audit Part 7 — tests & CI gaps.

Run full pytest. List skipped tests.
Identify paper claims (see checklist in docs/pre_publication_audit.md) with no automated test.

Report only: missing tests ranked CRITICAL / HIGH / MEDIUM. Do not fix yet.
```

- [x] Part 7 complete

---

## Part 8 — Publication surface

**Scope:** README, docs, git tracked files, paper availability section

**Run:**

```bash
git ls-files '*.nc'                   # should be empty on tipmip-gwl
rg -i 'cesm2|password|/work/bm' tipmip-gwl/
```

### Prompt

```
Audit Part 8 — publication surface (public tipmip-gwl + paper PDF in repo).

Check docs, README, pyproject.toml, tracked files; paper data-availability paragraph vs repo layout.
Ensure paper PDF co-location does not ship embargo data; no CESM2 in shipped products/docs.

Report only. Tag PAPER-DRIFT. Do not fix yet.
```

- [x] Part 8 complete

---

## Part 10 — Paper ↔ implementation traceability (dedicated)

Run after Parts 6, 1, 2, and 5 (or read their findings first).

**Scope:** Full paper draft PDF vs entire `src/tipmip_gwl/` + `paper/` + README/docs.

**Method:** Walk the [Paper claims checklist](#paper-claims-checklist-verify-in-part-10) line by line.
For each item: cite **paper section**, **code location**, and **pass/fail** (with PAPER-DRIFT detail on fail).

### Prompt

```
Audit Part 10 — paper ↔ implementation traceability.

Read: Paper draft_ TIPMIP temp-axis.pdf (full).
Read: docs/pre_publication_audit.md Paper claims checklist.
Cross-check every checklist item against code (src/tipmip_gwl/), paper scripts, committed figures/tables, README.

Produce a table: Claim | Paper section | Code/artifact | Status (OK / DRIFT / UNVERIFIED).
List all PAPER-DRIFT findings as CRITICAL/HIGH/MEDIUM with recommended fix (paper vs code).

Report only. Do not fix yet.
```

- [x] Part 10 complete

---

## Part 11 — Consolidated release checklist (after 1–8 and 10)

### Prompt

```
Consolidated pre-publication checklist for tipmip-gwl.

Read findings in docs/pre_publication_audit.md Findings log and Part 10 traceability table.

Dedupe findings; separate must-fix before submission vs can-fix post-release.
Include a "Paper fixes" section (text/captions/paths) vs "Code fixes".

Do not fix yet unless I say fix CRITICAL.
```

- [x] Consolidated checklist complete

---

## Findings log

Paste or append findings from each part here.

### Part 1

**Verdict: FAIL** — 2 CRITICAL, 4 HIGH, 8 MEDIUM, 6 nits. Agent: Opus thinking-high, 2026-07-30.

**Tests:** 78 passed (`test_mapping`, `test_baseline`, `test_product`, `test_rampdown`).

**Verified OK:** All 24 `gwlmap_*.nc` re-derive bit-exactly from stored `gmsat_anomaly`; grids 201/351 at 0.02 °C; baseline rules match paper; Tables A1/A2 match products; PCHIP + NaN beyond range; one baseline shared across legs per model.

#### CRITICAL

1. **Edge-shrunk 31-yr running mean** — PAPER-DRIFT. `running_mean` (`mapping.py:115-132`) shrinks window at record edges (~0.15 °C bias), not truly centred. Paper's explanation for ramp-up NaN floor ("smoothed anomaly already positive at branch") wrong for 6/8 models. Larger than all Sect. 2.3 sensitivities.

2. **Ramp-up grid stops at 4 °C; 7/8 models reach 4.2–11.1 °C** — PAPER-DRIFT. `_grid_bounds_warnings` only wired for ramp-down (`build.py:556`), not ramp-up. IPSL loses 358/590 years silently. `relabel_to_gwl` vs `resample_to_gwl` cover different ranges.

#### HIGH

3. **`branch_window_reference` no completeness check** — GISS 21-yr window labelled `branch_window_31yr` (confirms Part 6 #1).

4. **Ramp-down baseline silently reverts to full piControl mean** when no ramp-up product found; warning suppressed when `mapping_dir=None` (`build.py:348-379`).

5. **No `KNOWN_BRANCH_YEARS` fallback** — UKESM 2277 only in hand-patched attrs; rebuild from unpatched files → wrong baseline. AGENTS.md claim wrong.

6. **IPSL stale `KNOWN_BRANCH_YEARS`** — spurious `mapping_warnings` in shipped product (Part 6 #5 confirmed in v1 file).

#### MEDIUM (8)

7. `baseline_n_years` = full piControl length, not window size. 8. End-of-piControl centred window → uncaught `ValueError`. 9. `picontrol_reference(detrend=True)` misleading on partial NaN. 10. `mapping.resample_variable` clamps vs NaN (paper Step 3). 11. `running_mean` ignores year gaps. 12. Trailing method label hard-codes "31". 13. NorESM ramp-down drops branch-year caveat. 14. v1 built from two git revisions (ramp-up `ad1d627`, ramp-down `fbb67b5`).

#### nits (6)

15–20: interannual_std inflated; PAVA plateau year assignment; duplicate relabel coords; `map_model` default baseline; Sect. 2.2 "revisits full 0–4 °C" not literal; dead `provenance_check`.

**Top 3 science risks:** (1) edge-shrunk smoothing ~0.15 °C, (2) ramp-up truncated at 4 °C, (3) baseline provenance fragility (GISS/UKESM/IPSL/ramp-down fallback).

### Part 2

**Verdict: FAIL** — 1 CRITICAL, 4 HIGH, 8 MEDIUM, 8 nits. Agent: Opus thinking-high, 2026-07-30.

**Tests:** 17 passed (`test_product`); full suite 89 passed.

**Verified OK:** `relabel_to_gwl` / `resample_to_gwl` maths correct on decimal-year axes; NaN masks match; no extrapolation; leg names work; hysteresis preserved; spatial/multi-var OK.

#### CRITICAL

1. **`relabel_to_gwl` silently returns empty array for `datetime64` time axes** — PAPER-DRIFT (`product.py:477`). Paper Step 3 claims "any native resolution (annual, monthly, or finer)"; only numeric decimal-year works. Zero test coverage for `relabel_to_gwl`.

#### HIGH

2. **Ramp-down relabel gives descending `gwl` coordinate** — docstring says non-decreasing; `.sel(gwl=slice(1,2))` silently empty (`product.py:469-486`).

3. **`gwl_step=` breaks cross-leg point alignment** — PAPER-DRIFT. `_year_of_gwl_target` uses plain `np.arange` not `gwl_grid_rampdown`; Fig. 5 differencing silently all-NaN (`product.py:361-367`).

4. **Default mappings dir wrong for non-editable install** — `parents[2]` → site-packages path (`product.py:210-219`); Zenodo users get misleading warning.

5. **`relabel_to_gwl` has zero automated tests** (overlaps Part 7).

#### MEDIUM (8)

6. Non-unique relabelled `gwl` in 15/24 products. 7. Ramp-up truncated at 4 °C, no user warning (overlaps Part 1 #2). 8. Ramp-up files lack `leg` attr; both ramp-down legs → `leg='ramp-down'`. 9. README mislabels `resample_to_gwl`. 10. Docs vs paper on input resolution — PAPER-DRIFT. 11. Sub-annual anchor at Y.0 not mid-year (~0.5 yr lag). 12. No `year_offset` on resample. 13. Resample drops fractional source year coord.

#### nits (8)

14–21: dead code, CLI leg vocab mismatch, name conflicts, warning suppression, etc.

**Top 3 user-facing risks:** (1) silent empty relabel on CF time, (2) silent all-NaN cross-leg diff with `gwl_step=`, (3) install path + truncated ramp-up range.

### Part 3

**Verdict: PASS with findings** — 1 HIGH, 4 MEDIUM, 4 nits. Agent: Composer, 2026-07-30. **Tests:** 6 passed.

**Verified OK:** 8 models match paper Tables A1/A2; 24 v1 files; no CESM2 in products; `REQUIRED_GMSTMON_EXPERIMENTS` gating; builds fail on missing included model; `check_staged_gmstmon.py` OK locally.

#### HIGH

1. **`table_mono_max.py` weak completeness gate** — `bundled_models()` no-arg returns full list without checking files exist; partial mapping dir → short Table A2 with no error.

#### MEDIUM

2. NorESM `swl` typo in 2 filenames/attrs (confirmed). 3. GISS dn4 uses `r1i1p1f1` vs `f3` other legs (baseline inherited). 4. `require_mapping_index` dead code. 5. `build_all.py` silently skips ramp-down rebuild if dn dirs missing. 6. `discover()` last-wins on duplicate model files, no warning.

#### nits

7. Paper cover lists CESM2 co-author. 8–10: staging/ordering/test gaps.

### Part 4

**Verdict: FAIL** — 1 CRITICAL, 3 HIGH, 5 MEDIUM, 4 nits. Agent: Composer, 2026-07-30.

**Verified OK:** Zero `.nc` in public repo; 24 files in sibling mappings; embargo split clear in README; coordinate product only.

#### CRITICAL

1. **Non-editable install** — `default_mappings_dir()` resolves to site-packages path; Zenodo users need `TIPMIP_GWL_MAPPINGS` (undocumented).

#### HIGH

2. **Levante path mismatch** — PAPER-DRIFT: paper `/work/bm1448/tipmip-gwl-mappings` vs README `/work/bm1448/analysis/harteg/tipmip-gwl-mappings`. 3. **Sect. 3 implies mappings on public GitHub** — PAPER-DRIFT. 4. **`staged_data.md` pip-only wording** misleading.

#### MEDIUM

5. "Bundled" terminology throughout. 6. No Zenodo install docs in README. 7. Paper doesn't name sibling-layout convention. 8. Reproducibility vs manifest (Part 6). 9. `tracking_id` attr naming vs paper.

### Part 5

**Verdict: FAIL (captions/claims)** — 3 HIGH, 5 MEDIUM, 11 nits. Agent: Opus, 2026-07-30. **Build:** `build_all.py` exit 0, 41 s; **6/6 figures byte-identical**; 3/4 tables match (baseline_sensitivity CRLF-only diff).

#### HIGH — PAPER-DRIFT

1. **Fig 4 caption wrong colours** — says teal/orange for GFDL/MIROC; figure uses purple/gold (those colours are other models in Fig 3).

2. **Fig 3 caption** — "ends at realised warming range" true for 1/8 models; 7/8 truncated at 4 °C axis limit.

3. **"31-yr centred" smooth + branch-start explanation** — edge-shrunk window is real mechanism; paper's "already positive at branch" wrong for 7/8 models (confirms Part 1 CRITICAL #1).

#### MEDIUM

4. Table A1 CSV NorESM `ref_window`/`abs_dref` misleading vs printed table. 5. Fig 1(a) cropped at 220 yr / 4.5 °C unstated. 6. Fig 4 connecting line horizontal only, not to resampled value. 7. NorESM `swl` in 2 product filenames. 8. NorESM ramp-down `parent_experiment_id=piControl` passes silently.

#### Verified OK

Fig 3/4 relabel vs resample correct; Fig 5 hysteresis + mask; Fig 6 baseline panels; Table A2 exact; cos(lat) caption accurate for Fig 3.

### Part 7

**Verdict: FAIL** — 6 CRITICAL missing tests, 9 HIGH, 12 MEDIUM. Agent: Composer, 2026-07-30. **89 passed, 0 skipped** (12 would skip without mappings). **No CI.**

#### CRITICAL missing tests

1. Zero `relabel_to_gwl` tests (Part 2 CRITICAL). 2. Zero `load_gmsat_nc`/GMSAT tests (Part 6). 3. Edge-shrunk smoothing regression (Part 1). 4. Ramp-up >4 °C truncation (Part 1). 5. No GitHub Actions. 6. 14% tests skip without mappings clone.

#### HIGH (top)

7. GISS incomplete branch window. 8. UKESM 2277 fallback. 9. Ramp-down baseline silent fallback. 10. `gwl_step=` cross-leg alignment. 11. `mono_max`/Table A2 pipeline. 12–15: PCHIP weak coverage, exact 24-file count, baseline routing, py version matrix.

**Top 5 priorities:** relabel suite; load_gmsat_nc tests; Part 1 CRITICAL regressions; CI with mappings; Table A1/A2 golden files.

### Part 8

**Verdict: FAIL** — 1 CRITICAL, 3 HIGH, 5 MEDIUM, 4 nits. Agent: Composer, 2026-07-30.

**Verified OK:** No tracked `.nc`; no CESM2 in shipped code/docs; README/docs coherent.

#### CRITICAL

1. **Embargo mapping coordinates in committed notebook outputs** — `examples/resample_diagnostic.ipynb` contains full GFDL `gwl_axis`/`year_of_gwl` in executed cells. Clear outputs before public push.

#### HIGH

2. **Paper PDF internal cover pages** (CESM2, workflow notes) — don't track raw draft publicly. 3. **Levante path mismatch** (paper vs README). 4. **Zenodo DOI placeholders** unfilled.

#### MEDIUM

5. Sect. 3 "on github" ambiguity. 6. Notebook "bundled mapping" prose wrong. 7. No CI. 8. `.gitignore` gaps (draft PDF, audit doc). 9. CDO claim vs building_mappings.md.

### Part 6

**Verdict: FAIL** — 2 CRITICAL, 5 HIGH, 7 MEDIUM, 6 nits. Agent: Opus thinking-high, 2026-07-30.

**Tests:** `pytest tests/test_build_gmstmon.py tests/test_io.py` → 5 passed; full suite → 89 passed.

**Verified OK:** days-in-month weighting correct; all 18 tas gmstmon have `cdo fldmean` in history; staged files NaN-free, mid-month timestamps; **every Table A1 value reproduces exactly** from staged gmstmon.

#### CRITICAL

1. **GISS-E2-1-G-CC2 piControl missing 2150–2159** — PAPER-DRIFT. Nominal 31-yr centred window at branch 2156 is actually 21 years (2141–2149, 2160–2171). Manifest gap: no `215001-215912` chunk. No code warning; product still says `branch_window_31yr`. Impact ~0.006 K only, but Table A1 method/range claims wrong for GISS.

2. **Manifest cannot rebuild product** — zero rows for `esm-up2p0-gwl4p0-50y-dn2p0`; NorESM2-LM missing from dn2p0 (upstream `swl` typo). Documented Levante build aborts; ramp-down-4 °C leg not regenerable from committed inputs. Contradicts paper Sect. 3 reproducibility claim.

#### HIGH

3. **ACCESS-ESM1-5 piControl gmstmon built off-pipeline** (laptop/Downloads, Jul 2026) — provenance gap for the one model with special trailing baseline.

4. **UKESM branch metadata hand-written** via `fix_ukesm_branch_attrs.py`, not decoded from archive — PAPER-DRIFT; paper presents as `branch_time_in_parent` decode; no disclosure; overwrites `source_id`/`experiment_id`.

5. **Stale `KNOWN_BRANCH_YEARS["IPSL-CM6-ESMCO2"] = 1850`** — decoded 1849 used; spurious `mapping_warnings` in published IPSL product.

6. **`load_gmsat_nc` NaN handling** — denominator not masked; partial/all-NaN years can yield wrong or 0.0 K annual mean (latent; staged data clean).

7. **No test coverage** for `load_gmstmon` / days-in-month GMSAT definition (only 5 trivial tests).

#### MEDIUM (7)

8. `backend="auto"` can silently use xarray cos(lat) vs paper's unconditional CDO claim — PAPER-DRIFT (v1 files OK).
9. cos(lat) fallback omits lat-band width; `--areacella` ignored when CDO selected.
10. Chunks grouped by model only (member/table/grid not checked).
11. GISS uses `r1i1p1f3` for pi/up/dn2 but `r1i1p1f1` for dn4 — shared-baseline assumption?
12. NorESM mapping filenames carry upstream `swl` typo (2 of 24 files).
13. Incomplete years / end-of-month timestamps accepted silently (latent).
14. Dedupe drops `time_bnds`; NorESM/UKESM staged from older manifest state.

#### nits (6)

15–20: first-point dedupe tolerance; divergent model parsers; string chunk ordering; GISS `parent_source_id`; Windows tmp replace; UKESM `--include-mlotst` scope.

**Top 3 risks:** (1) GISS 21-yr baseline labelled 31-yr, (2) dn4 leg not rebuildable from manifest, (3) undisclosed UKESM/ACCESS provenance + IPSL warning in product.

### Part 10 (paper traceability)

**Verdict: FAIL (paper text)** — 3 CRITICAL, 6 HIGH, 11 MEDIUM PAPER-DRIFT. Agent: Opus, 2026-07-30.
**Counts:** 27 OK · 14 DRIFT · 2 UNVERIFIED (Zenodo DOIs).

#### Traceability summary

| Section | OK | DRIFT | Key failures |
|---------|-----|-------|--------------|
| Method (M1–M28) | 18 | 7 | Edge-shrunk smooth (M8/M26); 4 °C truncation (M19); relabel CF time (M20); UKESM decode (M7); GISS 21-yr window (M3) |
| Ensemble (E1–E8) | 5 | 3 | Sect. 3 regen claim (E5); Table A1 attrs overstated (E6); NorESM swl names (E8) |
| Robustness (R1–R9) | 6 | 3 | NorESM CSV (R2); window 3.3 vs 3.4 yr (R6); abstract "centred" (R8) |
| Figures (F1–F6) | 3 | 3 | Fig 1 crop; Fig 3 axis clip; Fig 4 colours |
| Data (D1–D7) | 2 | 3 | "on github" (D3); Levante path (D4); CDO unconditional (D6) |

#### CRITICAL PAPER-DRIFT

**P10-1** — "31-yr centred" smooth shrinks at edges; Sect. 2.2 wrong (7/8 models negative at branch). Fix: **paper** (mechanism) ± **code** (NaN outside full window = v2).

**P10-2** — Ramp-up grid stops at 4 °C; 7/8 models exceed (IPSL 11.06 °C, 358/590 yr dropped); no warning. Fix: **paper must** + wire `_grid_bounds_warnings` on ramp-up.

**P10-3** — Sect. 3 "data product on github" vs embargo split. Fix: **paper**.

#### HIGH PAPER-DRIFT

**P10-4** — `relabel_to_gwl` empty on datetime64 (Step 3 "monthly or finer"). Fix: **code** + paper qualifier.

**P10-5** — UKESM branch hand-patched; GISS 21-yr window. Fix: **paper caption + code**.

**P10-6** — Levante path wrong. Fix: **paper** or move dir.

**P10-7** — Fig 3/4 caption errors. Fix: **paper captions**.

**P10-8** — Product lacks full Table A1 diagnostics (`ref_full`, `|Δref|`). Fix: **code** or soften Sect. 3.

**P10-9** — ~~Notebook embargo residue~~ **RESOLVED** (2026-07-30): no mapping attrs/arrays in committed outputs; only `list_models()` + plot PNGs remain. Optional: add `nbstripout` pre-commit guard.

#### Resolved since earlier parts

- Part 1 #14 (two git revisions) — all 24 products now `8d643e4`.
- Part 8 CRITICAL #1 — **RESOLVED** (notebook cleanup verified 2026-07-30).

#### Top 5 submission blockers

1. Undocumented 4 °C ramp-up truncation (P10-2)
2. "Centred" smooth + wrong branch-start explanation (P10-1)
3. Data availability internal inconsistency + DOI placeholders (P10-3, P10-6)
4. ~~Notebook embargo residue (P10-9)~~ **RESOLVED**
5. Silent empty relabel on CF time (P10-4)

Full traceability table (43 rows): see agent report [Part 10](541b8182-c5a4-4581-8953-ac79f098d265).

### Must-fix before public push / GMD submission

<!-- Part 11 consolidated, 2026-07-30. 41 deduped items from Parts 1–8, 10. -->

**RESOLVED:** Notebook embargo (Part 8 CRITICAL #1, P10-9) — verified no `tracking_id`, `gwl_axis`, `year_of_gwl`, or `baseline_gmsat` in notebook; only `list_models()` output + 3 plot PNGs. Also resolved: all 24 products now `git_revision=8d643e4`.

| Bucket | CRITICAL | HIGH | Items |
|--------|----------|------|-------|
| Before public GitHub push | 2 | 7 | 12 |
| Before GMD submission | 4 | 9 | 19 |
| Should-fix (pre-submission if time) | 0 | 2 | 10 |
| Post-release | — | — | 2 clusters |

---

## A — Must-fix before public GitHub push

**Repo hygiene**
- [ ] Add `*.pdf`, `docs/pre_publication_audit.md` to `.gitignore`; `nbstripout` on `examples/` (prevent notebook regression)
- [ ] Do **not** track raw draft PDF (internal cover: CESM2, workflow notes)
- [ ] GitHub Actions: pytest on py3.10–3.12; flag mappings-dependent skips
- [ ] Add `CITATION.cff` before code Zenodo deposit
- [ ] Pre-push gate: `git log --all -- '*.nc' 'gwlmap_*'` empty; Part 8 greps clean

**Code**
- [ ] `relabel_to_gwl`: raise or support CF/`datetime64` time — no silent empty (P10-4)
- [ ] Fix `default_mappings_dir()` for pip/Zenodo install; document `TIPMIP_GWL_MAPPINGS`
- [ ] `gwl_step=` → use `gwl_grid_rampdown` for cross-leg alignment
- [ ] Wire `_grid_bounds_warnings` on ramp-up build path

**Docs**
- [ ] README + `staged_data.md`: Zenodo install path for mappings
- [ ] Fix README `resample_to_gwl` wording; drop "bundled mapping" in notebook prose
- [ ] Fix AGENTS.md `KNOWN_BRANCH_YEARS` UKESM claim

**Done**
- [x] Notebook embargo residue cleared

---

## B — Must-fix before GMD submission

**Paper (text, captions, paths)**
- [ ] **Edge-shrunk smooth** — replace "31-yr centred" + wrong branch-start explanation (7/8 models negative at branch)
- [ ] **4 °C ramp-up truncation** — state explicitly; most models exceed it (IPSL to 11 °C)
- [ ] Sect. 3: mappings **not** on public GitHub (embargo split)
- [ ] Fig 3, 4, 1(a) captions (axis clip, wrong colours, unstated crop)
- [ ] Levante path harmonise with README
- [ ] Fill both Zenodo DOIs
- [ ] Table A1 caption: GISS 21-yr window; UKESM hand-patched branch year
- [ ] Qualify CDO fldmean; fix 3.3 vs 3.4 yr window sweep
- [ ] Soften product-metadata claim OR add `ref_full`/`abs_dref` to NetCDF attrs
- [ ] If dn4 leg stays non-regenerable, soften Sect. 3 reproducibility claim

**Code + data**
- [ ] `branch_window_reference` completeness check (GISS)
- [ ] `KNOWN_BRANCH_YEARS` fallback for UKESM 2277; fix IPSL 1849 → rebuild product
- [ ] `table_mono_max.py` strict file-existence gate
- [ ] Manifest: add dn4 rows + NorESM dn2p0 (maintainer)
- [ ] Regenerate ACCESS piControl gmstmon on pipeline (provenance)

---

## C — Should-fix (pre-submission if time)

- [ ] Test suites: `relabel_to_gwl`, `load_gmsat_nc`, Part 1 CRITICAL regressions, Table A1/A2 golden files
- [ ] Ramp-down baseline silent fallback (`build.py:348-379`)
- [ ] Ramp-down relabel descending `gwl` coordinate
- [ ] `load_gmsat_nc` NaN denominator masking
- [ ] NorESM `swl` filename normalisation; GISS f1/f3 dn4 note
- [ ] Product `leg` attrs; `build_all.py` strict on missing dn dirs

---

## D — Post-release

Part 1 MEDIUM cluster (`baseline_n_years`, `resample_variable` clamping, etc.) + nits (dead code, CLI vocab, duplicate relabel coords).

---

## Top blockers (priority order)

1. Paper: edge-shrunk smooth + 4 °C truncation wording
2. Paper: data availability (GitHub vs Zenodo, Levante path, DOIs)
3. Code: `relabel_to_gwl` datetime64 + Zenodo install path
4. Maintainer: manifest dn4 / NorESM dn2 rebuildability
5. Repo: `.gitignore`, CI, no draft PDF in public repo

Full numbered list (41 items): see [Part 11 agent report](2be303a2-0491-4195-930c-10706bdf668e).

---

## Quick links

- [Paper draft (PDF)](../Paper%20draft_%20TIPMIP%20temp-axis.pdf)
- [using_mappings.md](using_mappings.md)
- [building_mappings.md](building_mappings.md)
- [staged_data.md](staged_data.md)
- [AGENTS.md](../AGENTS.md)
