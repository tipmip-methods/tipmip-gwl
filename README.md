# tipmip-gwl

Re-index TIPMIP ramp-up output from a **time** axis onto a common **global warming level (GWL)** axis.

1. Weighted annual-mean GMSAT for ramp-up and piControl
2. Full piControl mean as the anomaly baseline
3. Anomaly → smooth → enforce monotonicity → invert onto a common T-grid

```bash
pip install -e ".[plot]"

# build gmstmon (default manifest bundled in package)
tipmip-gwl-preprocess --exp esm-piControl --outdir gmstmon/

# sanity table + diagnostic figures
tipmip-gwl-diagnostics --up2p0-dir <dir> --picontrol-dir <dir> --plot --plotdir figures/

# the data product: one mapping .nc per mappable model
tipmip-gwl-build --up2p0-dir <dir> --picontrol-dir <dir> --outdir mapping/

# baseline sensitivity: full piControl mean vs legacy 31-yr window at branch year
python examples/baseline_sensitivity.py --up2p0-dir <dir> --picontrol-dir <dir>
```

The baseline uses the **full piControl mean** (not a centred window at branch year).
For the five mappable TIPMIP models, piControl drift is well below 0.5 °C/cy and
|ref_full − ref_window| is at most ~0.09 K — see `examples/baseline_sensitivity.py`.

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

A model is skipped (not written) only when it has no matching piControl tas on
disk. Wrong ``experiment_id`` or missing branch metadata are recorded as warnings.
A branch year outside the staged piControl span prevents mapping (and the 31-yr
branch reference).

### Using a mapping file

There are two GWL transforms, depending on whether you want a **shared** axis or
each model's **own** axis:

1. **`remap_to_gwl`** — resample a diagnostic onto the common 0–4 °C grid
   (0.1 °C steps, shared across models). Uses the inverse `year_of_gwl(gwl)`.
   Use this to **stack/compare models** at the same warming level.
2. **`relabel_to_gwl`** — relabel a model's *native* time axis with continuous
   GWL (its own, uneven, unbinned). Uses the forward `gwl_axis(year)`. Use this
   to **plot a single model** against GWL without losing temporal resolution.

`year_of_gwl(gwl)` is the operational variable for #1 — the model year at each
GWL. `remap_to_gwl` aligns by year *value* and returns NaN beyond the model's
range (never extrapolates):

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

Note: `remap_to_gwl` interpolates linearly in time between annual values, so an
abrupt mid-year change is smeared across the straddling GWL bin; supply a monthly
diagnostic if sub-annual timing matters. See `examples/remap_diagnostic.py`.

#### Relabel a single model's axis (transform #2)

`relabel_to_gwl` keeps every timestep and just swaps the coordinate values to the
warming level reached that year — no binning, native resolution. Good for
plotting one model against GWL:

```python
import xarray as xr
from tipmip_gwl import relabel_to_gwl

mp = xr.open_dataset("mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]  # 'year' axis

on_gwl = relabel_to_gwl(mp, diag)              # 'year' dim -> 'gwl' (native length)
on_gwl.mean("hp_pixel").plot()                  # x-axis is now GWL (°C)

# zero-based axis (e.g. a TOAD export starting at time=0): shift to calendar years
# and keep the original dim name so downstream tools still find it:
# on_gwl = relabel_to_gwl(mp, da, year_dim="time",
#                         year_offset=int(mp.attrs["rampup_start_year"]),
#                         new_dim=None)
```

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
# finer bins (use the same step for every model in MMA):
# on_gwl = remap_export_to_gwl(..., gwl_step=0.05)
# 'cluster' is now indexed by 'gwl' instead of 'time'; feed these to MMA.
```

Alignment is by calendar-year *value*. If your export already carries calendar
years on its time coordinate, omit `export_start_year`. The bin grid is set by
``gwl_step`` (default ``0.1`` degC) and ``gwl_max`` (default ``4.0``); it does
not have to match the 0.1 degC grid stored in the mapping file. Use the same
``gwl_step`` for all models in one MMA run. ``temporal_tolerance`` in MMA is in
bin index units, so finer bins mean a narrower physical window.

## Repository layout

```
src/tipmip_gwl/          Python package (mapping, baseline, preprocess, product, …)
  data/tas_chunks.tsv      Hand-maintained Levante paths for tas time chunks
docs/gmstmon_pipeline.md   GMSAT preprocessing guide
scripts/                   HPC helpers (Levante preprocess, PIK pull); see scripts/README.md
examples/                  Analysis scripts (mean_tas_piControl, baseline_sensitivity, …)
```

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
├── preprocess.py    Build gmstmon from raw tas chunks (`tipmip-gwl-preprocess`).
├── diagnostics.py   Driver that pairs ramp-up with piControl across models,
│                    prints the sanity table, and backs the CLI.
├── product.py       Build the per-model time<->GWL NetCDF product: transform,
│                    diagnostics, and provenance (backs `tipmip-gwl-build`), plus
│                    the two continuous transforms `remap_to_gwl` (shared grid)
│                    and `relabel_to_gwl` (native per-model axis).
├── regrid_export.py `remap_export_to_gwl`: forward-bin a categorical TOAD
│                    cluster export onto the common GWL grid before MMA.
└── plotting.py      Diagnostic figures (ramp-up anomaly overlay; per-model
                     piControl baseline panels). Needs the `plot` extra.

examples/
├── mean_tas_piControl.py       piControl baseline comparison figure
├── synthetic_demo.py           End-to-end run on synthetic data (no NetCDF needed).
├── remap_diagnostic.py         Apply a mapping file to a diagnostic variable.
├── baseline_sensitivity.py     Full piControl mean vs legacy 31-yr window baseline.
```
