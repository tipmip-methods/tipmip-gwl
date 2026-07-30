# Using mapping products

Install the package and load a bundled mapping — no separate NetCDF download.

```bash
pip install -e .
```

Mapping build detail: [building_mappings.md](building_mappings.md).

## Load a mapping

```python
from tipmip_gwl import load_mapping, list_models

print(list_models())  # eight Tier-1 models, mapping version v1

mp = load_mapping("GFDL-ESM2M")                              # ramp-up (default)
mp_dn = load_mapping("GFDL-ESM2M", leg="ramp-down-4c")       # ramp-down legs
```

Local rebuild instead of the bundled snapshot: `load_mapping(..., mapping_dir="mapping/")`
or explicit `path=`.

**Hysteresis caveat:** same GWL on ramp-up and ramp-down is a **different** Earth-system
state. Tag analyses by leg; do not treat up and down as interchangeable.

## Two transforms

| Function | Axis | Use when |
|----------|------|----------|
| `resample_to_gwl` | Shared grid (0–4 °C ramp-up; −2–5 °C ramp-down; 0.02 °C steps) | Compare or stack models at the same GWL |
| `relabel_to_gwl` | Native per-model GWL (uneven) | Plot one model without binning |

Both expect **annual** data on calendar years. Values are never extrapolated beyond each
model's realised range on that leg. `resample_to_gwl` linearly interpolates in time;
supply monthly data if sub-annual timing matters.

## Examples

**Resample one diagnostic:**

```python
import xarray as xr
from tipmip_gwl import load_mapping, resample_to_gwl

mp = load_mapping("GFDL-ESM2M")
diag = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]
on_gwl = resample_to_gwl(mp, diag)   # indexed by 'gwl'
```

**Ensemble stack:**

```python
import xarray as xr
from tipmip_gwl import load_mapping, list_models, resample_to_gwl

remapped = []
for name in list_models():
    mp = load_mapping(name)
    diag = xr.open_dataset(f"mlotst_{name}_esm-up2p0.nc")["mlotst"]
    remapped.append(resample_to_gwl(mp, diag).expand_dims(model=[name]))
ensemble = xr.concat(remapped, dim="model")
```

**Relabel (native resolution):**

```python
from tipmip_gwl import relabel_to_gwl

on_gwl = relabel_to_gwl(mp, diag)   # year dim → gwl; uneven spacing
```

Tutorial: [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).  
Paper figures using both transforms: [paper_figures.md](paper_figures.md).

## NetCDF contents

Each `gwlmap_*.nc` is a **coordinate product**: `year_of_gwl(gwl)`, `gwl_axis(year)`,
GMSAT anomaly fields, baseline scalars, and provenance attrs (`mapping_version`,
input `tracking_id`s). See [building_mappings.md](building_mappings.md) for build semantics.
