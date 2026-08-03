# Release todo

Open items only. Docs:
[using_mappings.md](using_mappings.md), [building_mappings.md](building_mappings.md),
[staged_data.md](staged_data.md), [paper_reproduction.md](paper_reproduction.md).

---

## Paper — co-author round

- [ ] Apply supervisor figure/layout feedback
- [ ] **Remove internal cover pages (pp. 1–2)** — co-author tables, CESM2/UKESM workflow notes; manuscript body starts p. 3
- [ ] Send PDF to co-authors

---

## Paper — before GMD submission

- [ ] **Zenodo DOI** — still `[Zenodo DOI]` in Data and code availability
- [ ] **Sect. 3 vs end matter:** Sect. 3 still says product carries “diagnostics (Table A1; Table A2)” on each file and “on github and … Levante”; end paragraph is better (GitHub + `mapping/`). Either soften Sect. 3 to match **or** add attrs to NetCDF
- [ ] **Levante path** — generic “DKRZ/Levante” only (optional unless you want a concrete path)
- [ ] **CDO fldmean** — Methods still state CDO unconditionally; code allows xarray fallback (one qualifying sentence if reviewers care)

---

## Package — before public GitHub / Zenodo

- [ ] Push and tag a release for the internal modelling group
- [ ] `.gitignore`: draft PDF, `.coverage`
- [ ] GitHub Actions: `pytest` on Python 3.10–3.12
- [ ] `CITATION.cff` before code Zenodo deposit
- [ ] Non-editable `pip install`: ship `mapping/` in the wheel **or** document `TIPMIP_GWL_MAPPINGS`
- [ ] Optional: `nbstripout` pre-commit on `examples/`
