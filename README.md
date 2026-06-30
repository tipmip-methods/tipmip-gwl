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

### Using a mapping file

`year_of_gwl(gwl)` is the operational variable — the model year at each GWL.
Apply it to your own diagnostic with `remap_to_gwl`, which aligns by year
*value* and returns NaN beyond the model's range (never extrapolates):

```python
import xarray as xr
from tipmip_gwl import remap_to_gwl

mp = xr.open_dataset("mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]  # on a 'year' axis
on_gwl = remap_to_gwl(mp, diag)            # now indexed by 'gwl', ready to stack
```

A fuller version — selecting levels and stacking models for ensemble statistics:

```python
import xarray as xr
from tipmip_gwl import remap_to_gwl

# one model: select a level or a window once it is on the GWL axis
mp = xr.open_dataset("mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]
on_gwl = remap_to_gwl(mp, diag)
print(on_gwl.sel(gwl=2.0))                 # diagnostic value at +2.0 °C
print(on_gwl.sel(gwl=slice(1.0, 2.0)))     # the 1–2 °C window

# if the diagnostic's annual axis is not called 'year', say so:
# on_gwl = remap_to_gwl(mp, diag, year_dim="time")

# many models: stack on the shared axis for ensemble statistics
models = {
    "GFDL-ESM2M": "mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc",
    "IPSL-CM6-ESMCO2": "mapping/gwlmap_IPSL-CM6-ESMCO2_esm-up2p0_v1.nc",
}
remapped = []
for name, path in models.items():
    mp = xr.open_dataset(path)
    diag = xr.open_dataset(f"mlotst_{name}_esm-up2p0.nc")["mlotst"]
    remapped.append(remap_to_gwl(mp, diag).expand_dims(model=[name]))

ensemble = xr.concat(remapped, dim="model")   # (model, gwl); NaN where unreached
print(ensemble.mean("model"))                  # ensemble mean vs GWL
print(ensemble.std("model"))                   # inter-model spread vs GWL
```

`gwl_axis(year)` is the *forward* map (GWL as a function of year), for plotting
and inspection only — not what you swap in as a coordinate. See
`examples/remap_diagnostic.py`. Note: the remap interpolates linearly in time
between annual values, so an abrupt mid-year change is smeared across the
straddling GWL bin; supply a monthly diagnostic if sub-annual timing matters.

### Remapping categorical cluster exports (for TOAD MMA)

`remap_to_gwl` interpolates and is only valid for *continuous* fields. Cluster
labels are categorical (`-1` = noise, `0,1,2,…` = events), so use
`remap_export_to_gwl`, which **forward-bins** instead: each export year is placed
in the GWL bin it reaches via `gwl_axis(year)`, and labels in a bin are reduced
per pixel (non-noise wins; ties → most frequent, then lowest id). Run shift
detection and clustering on each model's native annual axis, then remap only the
labels just before aggregation:

```text
shift detection → clustering → remap_export_to_gwl → MMA
```

```python
import xarray as xr
from tipmip_gwl import remap_export_to_gwl

mp = xr.open_dataset("mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc")
export = xr.open_dataset("clusters/GFDL-ESM2M_clusters.nc")  # TOAD_cluster_labels_v1

# TOAD exports usually zero-base time, so restore calendar years from the mapping:
on_gwl = remap_export_to_gwl(
    export, mp, export_start_year=int(mp.attrs["rampup_start_year"])
)
# 'cluster' is now indexed by 'gwl' instead of 'time'; feed these to MMA.
```

Alignment is by calendar-year *value*. If your export already carries calendar
years on its time coordinate, omit `export_start_year`.

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
│                    diagnostics, and provenance (backs `tipmip-gwl-build`), plus
│                    `remap_to_gwl` for continuous diagnostics.
├── regrid_export.py `remap_export_to_gwl`: forward-bin a categorical TOAD
│                    cluster export onto the common GWL grid before MMA.
└── plotting.py      Diagnostic figures (ramp-up anomaly overlay; per-model
                     piControl baseline panels). Needs the `plot` extra.

examples/
├── synthetic_demo.py    End-to-end run on synthetic data (no NetCDF needed).
├── remap_diagnostic.py  Apply a mapping file to a diagnostic variable.
└── figures/             Diagnostic figures used in the paper.
```
