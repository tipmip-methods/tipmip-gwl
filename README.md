# tipmip-gwl

Re-index TIPMIP ramp-up and ramp-down output from **calendar time** onto a **global warming level (GWL)** axis so models can be compared at the same warming rather than the same year.

```bash
pip install -e .
```

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

Worked example with a synthetic diagnostic:
[examples/resample_diagnostic.ipynb](examples/resample_diagnostic.ipynb).

**Users:** [docs/using_mappings.md](docs/using_mappings.md) — API reference.  
**Maintainers:** [docs/building_mappings.md](docs/building_mappings.md) and [docs/staged_data.md](docs/staged_data.md).

## Bundled mappings

Mapping version `v1` ships inside the package — no separate download:

- **8 ramp-up** (`load_mapping(model)`)
- **16 ramp-down** (`leg="ramp-down-2c"` or `"ramp-down-4c"`)

Each file is a **coordinate product** (`year_of_gwl`, `gwl_axis`, baseline metadata), not remapped fields. Per-model baseline details: `paper/tables/table_baseline_diagnostics.csv` (Appendix A1).

Monotone GWL axes for ramp-up and ramp-down

## Install extras

Paper reproduction and tests: `pip install -e ".[paper,test]"` (see [pyproject.toml](pyproject.toml)).

## Citation

Cite the accompanying GMD paper (in preparation) and pin `tipmip_gwl.__version__` and mapping version `v1`.

## License

BSD-2-Clause — see [LICENSE](LICENSE).