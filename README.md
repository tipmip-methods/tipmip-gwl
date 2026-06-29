# tipmip-gwl

Re-index TIPMIP ramp-up output from a **time** axis onto a common **global warming level (GWL)** axis.

1. Weighted annual-mean GMSAT for ramp-up and piControl
2. 31-yr centred piControl baseline at the branch year
3. Anomaly → smooth → enforce monotonicity → invert onto a common T-grid

```bash
pip install -e ".[plot]"

# sanity table + diagnostic figures
tipmip-gwl-diagnostics --up2p0-dir <dir> --picontrol-dir <dir> --plot

# the data product: one mapping .nc per mappable model
tipmip-gwl-build --up2p0-dir <dir> --picontrol-dir <dir> --outdir mapping/
```

## Data product

The deliverable is one NetCDF file per model (`gwlmap_<model>_esm-up2p0_<version>.nc`)
holding the coordinate transform, not remapped variables — users apply the axis
to their own diagnostic variable.

- `year_of_gwl(gwl)` — model year at each GWL on the common 0–4 °C grid (NaN beyond range).
- `gwl_axis(year)` — forward GWL(t): the monotone axis that was inverted.
- `gmsat_anomaly(year)`, `gmsat_anomaly_smoothed(year)` — the (un)smoothed anomaly.
- Scalar diagnostics: `baseline_gmsat`, `branch_year`, `picontrol_drift`,
  `monotonization_max`, `max_gwl_reached`, `baseline_method`.
- Provenance attrs: input `tracking_id`s, parent run, code version, git revision,
  `mapping_version` — so a downstream analysis can pin one exact axis.

A model is skipped (not written) when it fails provenance, has no piControl, or
branches outside the available control span.

## File overview

```
src/tipmip_gwl/
├── mapping.py       Pure numpy/scipy algorithm: baseline → anomaly → monotone
│                    temperature axis → invert → resample. Works on plain
│                    (years, values) arrays; no file-format knowledge.
├── io.py            Read global-mean tas NetCDF (days-in-month weighted annual
│                    mean) and discover model files in a directory.
├── baseline.py      Establish each model's anomaly zero point: TIPMIP
│                    provenance gate, branch-year decode from CMIP metadata,
│                    and the protocol piControl reference (with drift).
├── diagnostics.py   Driver that pairs ramp-up with piControl across models,
│                    prints the sanity table, and backs the CLI.
├── product.py       Build the per-model time<->GWL NetCDF product: transform,
│                    diagnostics, and provenance. Backs `tipmip-gwl-build`.
└── plotting.py      Diagnostic figures (ramp-up anomaly overlay; per-model
                     piControl baseline panels). Needs the `plot` extra.

examples/
├── synthetic_demo.py   End-to-end run on synthetic data (no NetCDF needed).
└── figures/            Diagnostic figures used in the paper.
```
