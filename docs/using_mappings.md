# Using mapping products

Load a bundled mapping and apply it to your own **annual** diagnostic — scalar,
regional, or spatially resolved. Mapping NetCDFs live in sibling repo
``tipmip-gwl-mappings`` (see README). Only the time axis is re-indexed; other
dimensions pass through unchanged.

## Load a mapping

```python
from tipmip_gwl import load_mapping, list_models

print(list_models())  # eight Tier-1 models, mapping version v1

mp = load_mapping("GFDL-ESM2M")                        # xr.Dataset, ramp-up
mp_dn = load_mapping("GFDL-ESM2M", leg="ramp-down-4c") # xr.Dataset, ramp-down
```

Local rebuild instead of the bundled snapshot: `load_mapping(..., mapping_dir="mapping/")`
or explicit `path=`. Each mapping is an **xarray Dataset** with coordinates
`year_of_gwl(gwl)` and `gwl_axis(year)` — pass it to `resample_to_gwl` /
`relabel_to_gwl`.

**Hysteresis caveat:** same GWL on ramp-up and ramp-down is a **different** Earth-system
state. Tag analyses by leg; do not treat up and down as interchangeable.

## Two transforms

| Function | Axis | Use when |
|----------|------|----------|
| `resample_to_gwl` | Shared grid (0–4 °C ramp-up; −2–5 °C ramp-down; 0.02 °C steps) | Compare or stack models at the same GWL |
| `relabel_to_gwl` | Native per-model GWL (uneven) | Plot one model without binning |

Both expect calendar-year coordinates. Values are never extrapolated beyond each model's
realised range on that leg. `resample_to_gwl` linearly interpolates in time.

`relabel_to_gwl` preserves input values but the GWL coordinate is **unevenly spaced**
(a 31-year running mean of annual GMSAT). Do not smooth after relabelling; use
`resample_to_gwl` when you need a uniform grid.

## Examples

**Resample a diagnostic:**

```python
import xarray as xr
from tipmip_gwl import load_mapping, resample_to_gwl

mp = load_mapping("GFDL-ESM2M")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]  # (year, lat, lon)
on_gwl = resample_to_gwl(mp, diag)   # (gwl, lat, lon)
```

**Relabel (native resolution):**

```python
from tipmip_gwl import relabel_to_gwl

on_gwl = relabel_to_gwl(mp, diag)   # year dim → gwl; uneven spacing
```

Tutorial: [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).

## NetCDF contents

Each `gwlmap_*.nc` is a **coordinate product**: `year_of_gwl(gwl)`, `gwl_axis(year)`,
GMSAT anomaly fields, baseline scalars, and provenance attrs. Build semantics:
[building_mappings.md](building_mappings.md).
