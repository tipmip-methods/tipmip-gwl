# tipmip-gwl

Re-index TIPMIP ramp-up and ramp-down output from **calendar time** onto a **global warming level (GWL)** axis so models can be compared at the same warming rather than the same year.

## Install

```bash
git clone https://github.com/tipmip-methods/tipmip-gwl.git
cd tipmip-gwl
pip install -e .
```

**Mapping products** (`gwlmap_*_v1.nc`) are **not** in this repository — TIPMIP
data remain under embargo. Clone or copy the separate data repo as a **sibling**
directory:

```text
parent/
  tipmip-gwl/
  tipmip-gwl-mappings/    # 24 NetCDF coordinate products (v1)
```

TIPMIP collaborators with Levante access:

```bash
scp -r levante:/work/bm1448/analysis/harteg/tipmip-gwl-mappings ../tipmip-gwl-mappings
```

Others: request access via the GMD review Zenodo record (embargoed until TIPMIP
release) or contact the authors.

Override the search path: `export TIPMIP_GWL_MAPPINGS=/path/to/mappings`.

## Quick use

```python
import xarray as xr
from tipmip_gwl import load_mapping, resample_to_gwl

# Mapping product: xarray Dataset (year_of_gwl, gwl_axis, baseline metadata)
mp = load_mapping("GFDL-ESM2M")

# Your annual variable: xarray DataArray (or Dataset) with a "year"
# dimension — global mean, regional index, or full grid (lat/lon, etc.)
diagnostic = xr.open_dataset("mlotst_GFDL-ESM2M_esm-up2p0.nc")["mlotst"]  # (year, …)

# Same values; "year" replaced by shared GWL coordinate (0.02 °C steps)
on_gwl = resample_to_gwl(mp, diagnostic)  # (gwl, …)
```

Worked example: [examples/resample_diagnostic.ipynb](examples/resample_diagnostic.ipynb).

**Users:** [docs/using_mappings.md](docs/using_mappings.md) — API reference.  
**Maintainers:** [docs/building_mappings.md](docs/building_mappings.md) and [docs/staged_data.md](docs/staged_data.md).

## Mapping products (v1)

When `tipmip-gwl-mappings` is installed alongside this repo:

- **8 ramp-up** (`load_mapping(model)`)
- **16 ramp-down** (`leg="ramp-down-2c"` or `"ramp-down-4c"`)

Each file is a **coordinate product** (`year_of_gwl`, `gwl_axis`, baseline metadata), not remapped fields. Per-model baseline details: `paper/tables/table_baseline_diagnostics.csv` (Appendix A1).

![Monotone GWL axes for ramp-up and ramp-down](paper/figures/fig_mapping_axis_up_down.png)

## Install extras

Paper reproduction and tests: `pip install -e ".[paper,test]"` (see [pyproject.toml](pyproject.toml)).

## Citation

Cite the accompanying GMD paper (in preparation) and pin `tipmip_gwl.__version__` and mapping version `v1`.

## License

BSD-2-Clause — see [LICENSE](LICENSE).
