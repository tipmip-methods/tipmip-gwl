# Publication todo

Derived from [`pre_publication_audit.md`](pre_publication_audit.md).  
**Strategy:** paper first (co-authors) → repo for internal use → GMD submission polish → defer optional items.

**Done:** notebook embargo cleared; mappings at `git_revision=8d643e4`; Sect. 3 no mappings on public GitHub;
**text edits for decisions #1, #2, #3, #6, #7 applied to the paper draft** — see
[`paper_drop_ins.md`](paper_drop_ins.md) for the line-by-line checklist (12/16 items applied, 3 skipped by
choice, 1 still pending); `resample_to_gwl` now clamps + warns instead of silently returning NaN beyond a
mapping file's stored GWL range (code fix, tests added, no mapping rebuild needed).

---

## Phase A — Co-author draft (paper only) ← **you are here**

Goal: PDF you can send to co-authors and your supervisor. **No repo or mapping rebuilds** unless you explicitly choose otherwise after a decision chat.

### A1. Your supervisor’s plot comments

- [ ] Apply supervisor feedback (figures/layout) — separate from audit; do first while you have context

### A2. Manuscript hygiene

- [ ] Remove internal cover pages (CESM2 table, “problematic models” workflow notes) — see `paper_drop_ins.md`

### A3. Audit paper fixes (no code)

- [x] **Fig. 3 caption:** panel (b) limited to 4 °C — fixed, no longer claims lines “end at realised warming range”
- [x] **Fig. 1(a) caption:** notes crop at 220 yr / 4.5 °C
- [x] **4 °C product limit:** Methods sentence added (decision #2) + `resample_to_gwl` now warns rather than silently truncating
- [x] **Edge-shrunk smooth + branch-start text:** Sect. 2.1–2.2 wording fixed (decision #1)
- [x] **Step 3:** calendar-year time coordinate qualifier added (decision #3)
- [ ] **Sect. 3:** Table A1 fields on the NetCDF files — **skipped for now** (decision #4; see below)
- [x] **Table A1 footnotes:** GISS 21-yr window; UKESM branch from modelling group (decisions #6/#7)

### A4. Can wait until after co-author round

- [ ] Zenodo DOIs (placeholders OK for internal circulation)
- [ ] Final GitHub URL (if repo not public yet)
- [ ] Levante path harmonised with README — **skipped for now** (decision #5; see below)

---

## Phase B — Internal package (after co-author draft stabilises)

Goal: colleagues can `pip install` and use mappings on Levante/laptop. Not necessarily public GitHub yet.

- [ ] README: how to install + point `TIPMIP_GWL_MAPPINGS` at local clone
- [ ] `staged_data.md` + docs: fix “bundled” wording
- [ ] README: fix `resample_to_gwl` example comment
- [ ] `.gitignore` if sharing repo internally (PDF, audit docs, `.coverage`)
- [ ] Confirm no mapping `.nc` in git history

**Defer for internal v1 unless someone hits a bug:** Wave 2–3 code fixes, tests, CI, CITATION.cff.

---

## Phase C — GMD submission (after co-authors sign off)

- [ ] Fill Zenodo DOIs; final GitHub URL
- [ ] **Levante path** — revisit decision #5 (skipped for co-author draft; fix before submission)
- [ ] **Sect. 3 Table A1/NetCDF wording** — revisit decision #4 (skipped for co-author draft; fix before submission)
- [ ] **Reproducibility wording (#10):** either soften Sect. 3 **or** fix maintainer manifest (Wave 4) — decide before submission, not necessarily before co-authors
- [ ] Public GitHub push checklist (if not already public)

---

## Deferred — optional (not now)

All Wave 2–5 code polish, CDO qualification, ACCESS/NorESM provenance rebuilds, IPSL rebuild, relabel CF-time implementation, CI, golden tests, etc. See audit doc if needed later.

---

## Decisions — status

| # | Topic | Status |
|---|--------|--------|
| **1** | Edge-shrunk smooth | ✅ Applied — paper text fixed; code keeps edge-shrunk window |
| **2** | 4 °C ramp-up cap | ✅ Applied — Methods sentence + `resample_to_gwl` clamp/warn |
| **3** | CMIP time / relabel | ✅ Applied — one line in Step 3 |
| **4** | Table A1 on NetCDF | ⏭️ **Skipped for co-author draft** — original wording kept; revisit before submission (Phase C) |
| **5** | Levante path | ⏭️ **Skipped for co-author draft** — original wording kept; revisit before submission (Phase C) |
| **6** | GISS 21-yr window | ✅ Applied — Table A1 footnote |
| **7** | UKESM 2277 | ✅ Applied — Table A1 footnote |
| **10** | Full reproducibility | Still open — decide before **submission**, not co-authors |
| 8–9, 11–16 | Provenance, rebuilds, API nits | No — deferred |

---

## Resolved: #1 edge-shrunk smooth

Paper text now describes the truncated (not fully centred) window at leg edges and the corrected
branch-start explanation. Code unchanged — edge-shrunk windows kept deliberately (no data loss at leg
ends; ~0.15 °C effect at edges, accepted). See `paper_drop_ins.md` for the exact wording applied.

## Resolved: #2 ramp-up stops at 4 °C

Methods now states the inverse map / `resample_to_gwl` output is limited to 0–4 °C even though most
models warm further on the monotone axis; Fig. 3 caption fixed to match. `resample_to_gwl` itself now
clamps a wider request back to the stored range with a warning instead of silently returning NaN.

---

## Next up

1. Supervisor plot changes
2. Strip internal cover pages (pages 1–2)
3. Send PDF to co-authors
4. Phase B when you want internal `pip install`

---

*Text-edit tracking: [`paper_drop_ins.md`](paper_drop_ins.md). Audit source: [`pre_publication_audit.md`](pre_publication_audit.md)*
