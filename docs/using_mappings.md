# Using mapping products

Apply a published ramp-up mapping to your own diagnostic variable. Install the
package and load a bundled mapping — no separate NetCDF download is required.

For how mappings are built from tas, see [building_mappings.md](building_mappings.md).

## Load a mapping

```python
from tipmip_gwl import load_mapping, list_models

print(list_models())
# ['ACCESS-ESM1-5', 'EC-Earth3-ESM-1', 'GFDL-ESM2M', ...]

mp = load_mapping("GFDL-ESM2M")
```

**Ramp-down** (bundled alongside ramp-up; use `leg=` to select):

```python
mp_dn2 = load_mapping("GFDL-ESM2M", leg="ramp-down-2c")
mp_dn4 = load_mapping("GFDL-ESM2M", leg="ramp-down-4c")
print(list_models(leg="ramp-down-2c"))
```

To use locally rebuilt files instead of the bundled snapshot, pass
`mapping_dir="mapping/"`.

Long CMIP experiment ids and explicit `path=` are optional escape hatches.

To use a locally rebuilt ramp-up file instead:

```python
mp = load_mapping("GFDL-ESM2M", mapping_dir="mapping/")
# or: mp = load_mapping("GFDL-ESM2M", path="mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc")
```

**Important:** same GWL on the ramp-up and ramp-down legs is a **different**
Earth-system state. Tag analyses by leg; do not stack up and down at the same GWL
as if they were interchangeable.

## Continuous diagnostics: two transforms

There are two GWL transforms, depending on whether you want a **shared** axis or
each model's **own** axis:

1. **`resample_to_gwl`** — resample onto the mapping's common GWL grid (0–4 °C
   at 0.02 °C steps for ramp-up; −2–5 °C at the same spacing for ramp-down).
   Uses the
   inverse `year_of_gwl(gwl)`. Use this to **stack or compare models** at the
   same warming level on one leg.
2. **`relabel_to_gwl`** — relabel a model's native time axis with continuous GWL
   (uneven, unbinned). Uses the forward `gwl_axis(year)`. Use this to **plot a
   single model** against GWL without losing temporal resolution.

`resample_to_gwl` aligns by calendar-year *value* and returns NaN beyond the
model's realised range (never extrapolates). It linearly interpolates in time
between annual values, so an abrupt mid-year change is smeared across the
straddling GWL bin; supply a monthly diagnostic if sub-annual timing matters.

`resample_to_gwl` is for **continuous** fields only. Categorical cluster-label
exports are handled in TOAD (`toad.regridding.gwl_export`).

### `resample_to_gwl` — single model

```python
import xarray as xr
from tipmip_gwl import load_mapping, resample_to_gwl

mp = load_mapping("GFDL-ESM2M")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]  # on a 'year' axis
on_gwl = resample_to_gwl(mp, diag)            # now indexed by 'gwl', ready to stack
print(on_gwl.sel(gwl=2.0))                 # value at +2.0 °C
print(on_gwl.sel(gwl=slice(1.0, 2.0)))     # the 1–2 °C window

# if the annual axis is not called 'year':
# on_gwl = resample_to_gwl(mp, diag, year_dim="time")
```

### `resample_to_gwl` — ensemble stack

```python
import xarray as xr
from tipmip_gwl import load_mapping, list_models, resample_to_gwl

remapped = []
for name in list_models():
    mp = load_mapping(name)
    diag = xr.open_dataset(f"mlotst_{name}_esm-up2p0.nc")["mlotst"]
    remapped.append(resample_to_gwl(mp, diag).expand_dims(model=[name]))

ensemble = xr.concat(remapped, dim="model")   # (model, gwl); NaN where unreached
print(ensemble.mean("model"))
print(ensemble.std("model"))
```

See also [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb)
for a minimal runnable tutorial.

### `relabel_to_gwl` — native axis

```python
import xarray as xr
from tipmip_gwl import load_mapping, relabel_to_gwl

mp = load_mapping("GFDL-ESM2M")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]

on_gwl = relabel_to_gwl(mp, diag)              # 'year' dim -> 'gwl' (native length)
on_gwl.mean("hp_pixel").plot()

# zero-based axis (e.g. export whose time starts at 0):
# on_gwl = relabel_to_gwl(mp, da, year_dim="time",
#                         year_offset=int(mp.attrs["rampup_start_year"]),
#                         new_dim=None)
```

Paper figures illustrating both transforms on mixed-layer depth:
[paper_figures.md](paper_figures.md) (`diagnostic_remap_demo.py`,
`diagnostic_remap_binned_demo.py`).

## Product file contents (reference)

Each `gwlmap_*.nc` includes:

- `year_of_gwl(gwl)` — model year at each GWL on the common grid (NaN beyond range)
- `gwl_axis(year)` — forward GWL(t) on the native year axis
- `gmsat_anomaly(year)`, `gmsat_anomaly_smoothed(year)`
- Scalars: `baseline_gmsat`, `branch_year`, `picontrol_drift`, `monotonization_max`,
  `max_gwl_reached`, `baseline_method`
- Provenance: input `tracking_id`s, parent run, code version, git revision,
  `mapping_version`

When branch metadata is missing or out of span, `baseline_method` is
`full_piControl_mean_no_branch_year` or `full_piControl_mean` respectively, and
`branch_year` may be NaN.
