Drop-in text for the co-author PDF. Each block is meant to **replace** the matching passage in your draft (search for the opening phrase if line breaks differ).

---

- [x] **Step 2 — smoothing (Sect. 2.1)**

**Replace:**

> We apply a 31-year centred running mean to the anomaly series of each leg. Smoothing is necessary because interannual variability…

**With:**

> We apply a 31-year centred running mean to each leg’s anomaly series. Where a full centred window would extend past the start or end of the leg, the window is truncated to the available years. The outer ~15 years of each leg use shorter effective windows and are therefore less smoothed than the interior. Smoothing is necessary because interannual variability…

*(Keep the rest of the paragraph from “Smoothing is necessary…” unchanged.)*

---

- [x] **Step 2 — summary bullet (start of Sect. 2)**

**Replace:**

> 1. Step 2 (Smoothing and monotonicity): apply a 31-year running mean, then enforce monotonicity via isotonic regression (PAVA), giving the smooth, monotone axis GWL(t).

**With:**

> 1. Step 2 (Smoothing and monotonicity): apply a 31-year centred running mean (truncating the window at leg edges where a full 31-year centred average is not available), then enforce monotonicity via isotonic regression (PAVA), giving the smooth, monotone axis GWL(t).

---

- [x] **Sect. 2.2 — branch start / minimum GWL (replace final paragraph)**

**Replace:**

> On ramp-up, the monotone axis typically begins slightly above 0 °C because the smoothed anomaly at branch start is already positive; t(0) is therefore undefined and remapped diagnostics are not available below that leg's realised minimum GWL.

**With:**

> On ramp-up, the monotone axis often begins slightly above 0 °C even when the raw annual anomaly at the branch instant is near zero or negative. At the leg start the running mean uses a shortened window over the earliest years of warming, so the first axis value reflects early post-branch warming rather than the unsmoothed anomaly at a single calendar year. Consequently t(0) is undefined on the monotone axis and remapped diagnostics are not available below each model’s realised minimum GWL on that leg. The resampling grid for ramp-up begins at 0 °C, but values below a model’s realised minimum remain NaN.

---

- [x] **Sect. 2.2 — “revisits full 0–4 °C” (optional tighten)**

**Replace:**

> The branch from 4 °C revisits the full 0–4 °C interval on the cooling leg and is the natural counterpart to ramp-up for hysteresis-style comparisons;

**With:**

> The branch from 4 °C spans much of the 0–4 °C interval on the cooling leg (over the staged run length) and is the natural counterpart to ramp-up for hysteresis-style comparisons;

---

- [x] **Resampling paragraph — 4 °C product limit (Sect. 2.1, Step 3)**

**Insert after:**

> For ramp-up the grid runs from 0 to 4°C in 0.02°C steps (201 points).

**Add:**

> The inverse map is tabulated on this 0–4 °C grid only (seven of eight models warm further on the monotone axis; Fig. 1a). Relabelling with the forward transform GWL(t) uses the full leg; `resample_to_gwl` can narrow this grid or change its spacing, but a request beyond 0–4 °C is clamped back to it with a warning, since the inverse map has no data outside that range.

---

- [x] **Step 3 — relabelling (calendar-year qualifier)**

**Replace:**

> The diagnostic being remapped can be supplied at any native resolution (annual, monthly, or finer) and each of its time steps is assigned a GWL by linear interpolation in calendar time between the two nearest annual anchors;

**With:**

> The diagnostic being remapped can be supplied at any native resolution (annual, monthly, or finer); each time step is assigned a GWL by linear interpolation in calendar time between the two nearest annual anchors. Time coordinates in the accompanying software must be numeric calendar years, not datetime objects.

---

- [x] **Sect. 2.3 — window sensitivity (3.3 → 3.4)**

**Replace:**

> Varying the smoothing-window length between 21, 31, and 41 years shifts the year assigned to a fixed GWL by at most about 3.3 years across all eight models

**With:**

> Varying the smoothing-window length between 21, 31, and 41 years shifts the year assigned to a fixed GWL by at most about 3.4 years across all eight models

---

- [ ] ~~**Sect. 3 — soften NetCDF vs Table A1 claims**~~

**Replace:**

> Each file also carries the per-model diagnostics (Table A1; Table A2) and is written to be CF-compliant and loadable like the rest of the archive.

**With:**

> Each file carries the leg’s GWL axis, inverse map on the fixed grid, baseline reference, piControl drift, and monotonicity diagnostic (Table A2). The baseline sensitivity quantities in Table A1 (full-run versus branch-window reference and |Δref|) are computed in the paper reproduction workflow and are not duplicated as separate global attributes on every NetCDF file. Products are written to be CF-compliant and loadable like the rest of the archive.

---

- [ ] ~~**Sect. 3 — data availability wording**~~

**Replace:**

> We publish the result as a data product on github and alongside the TIPMIP datasets on DKRZ/Levante, so that downstream analyses can adopt a common mapping rather than each reconstructing one.

**With:**

> We publish the result as a versioned mapping product, distributed via restricted-access Zenodo and DKRZ/Levante for data-access holders (see *Data and code availability*), so that downstream analyses can adopt a common mapping rather than each reconstructing one.

---

- [ ] ~~**Data and code availability — fix Levante path**~~

**Replace:**

> TIPMIP data-access holders can additionally obtain the files directly from Levante (`/work/bm1448/tipmip-gwl-mappings`).

**With:**

> TIPMIP data-access holders can additionally obtain the files directly from Levante (`/work/bm1448/analysis/harteg/tipmip-gwl-mappings`).

*(Matches the path in your README; this is the only place the paper states the Levante path in full detail, so fixing it here is decision #5.)*

---

- [x] **Figure 1 caption**

**Replace:**

> Figure 1. Monotone global-warming-level (GWL) axes for the ramp-up and ramp-down legs. GMSAT anomaly for each of the eight Tier 1 TIPMIP ESMs, plotted against years since the start of the respective leg: (a) ramp-up (esm-up2p0); (b) ramp-down after a 50-year zero-emission hold at 2 and 4 °C GWL (both branches overlaid). Thin lines show the days-in-month-weighted annual-mean anomaly; thick lines show the monotone axis used for re-indexing (31-year centred running mean and isotonic regression; increasing on ramp-up, decreasing on ramp-down; Sect. 2). Anomalies are referenced to each model's own piControl baseline (Fig. 2).

**With:**

> Figure 1. Monotone global-warming-level (GWL) axes for the ramp-up and ramp-down legs. GMSAT anomaly for each of the eight Tier 1 TIPMIP ESMs, plotted against years since the start of the respective leg: (a) ramp-up (esm-up2p0); (b) ramp-down after a 50-year zero-emission hold at 2 and 4 °C GWL (both branches overlaid). Panel (a) is cropped at 220 years and 4.5 °C for readability; several models continue warming beyond these limits on the full axis (e.g. IPSL-CM6-ESMCO2 above 10 °C). Thin lines show the days-in-month-weighted annual-mean anomaly; thick lines show the monotone axis used for re-indexing (31-year centred running mean with edge-shortened windows at leg ends, then isotonic regression; increasing on ramp-up, decreasing on ramp-down; Sect. 2). Anomalies are referenced to each model's own piControl baseline (Fig. 2).

---

- [x] **Figure 3 caption**

**Replace:**

> …values are not extrapolated beyond each model's realised warming range, so lines end at different GWLs.

**With:**

> …values are not extrapolated beyond each model's realised warming range on the forward axis. Panel (b) is displayed for 0–4 °C to match the ramp-up resampling grid; curves for models that warm past 4 °C are truncated at the axis limit (full axis in Fig. 1a).

---

- [x] **Figure 4 caption**

**Replace:**

> Global-mean annual-maximum mixed-layer depth for two models (GFDL-ESM2M, teal; MIROC-ES2L, orange) over a narrow GWL range,

**With:**

> Global-mean annual-maximum mixed-layer depth for two models (GFDL-ESM2M, purple; MIROC-ES2L, gold; colours as in Fig. 3) over a narrow GWL range,

---

- [x] **Table A1 caption — add footnotes at end**

**Append to Table A1 caption:**

> GISS-E2-1-G-CC2: staged piControl omits calendar years 2150–2159, so the nominal 31-year window centred on branch year 2156 spans 21 years only (2141–2149 and 2160–2171); |Δref| remains small (0.020 K). UKESM1-2-LL: branch year 2277 was not present in the archived CMIP6 metadata and was supplied by the UKESM modelling group for the staged files used here; it matches the value used in the TIPMIP protocol for this model.

---

- [x] **Table A2 caption — edge windows**

**Replace:**

> …after the 31-yr centred running mean, for the ramp-up leg

**With:**

> …after the 31-yr centred running mean (edge-shortened where a full window is unavailable), for the ramp-up leg

---

- [ ] **Internal pages 1–2 — delete for co-author PDF**

Remove pages 1–2 entirely (V3 draft notes, problematic-models table, co-author checklist). Start the circulated PDF at the title page (current page 3).