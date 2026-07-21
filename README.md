# tipmip-gwl

Re-index TIPMIP ramp-up output from **calendar time** onto a **global warming level (GWL)** axis so models can be compared at the same warming rather than the same year.

Install the package, load a bundled mapping, and apply it to your own annual diagnostic:

```bash
pip install -e .
```

```python
from tipmip_gwl import load_mapping, list_models, resample_to_gwl, relabel_to_gwl

print(list_models())
# ['ACCESS-ESM1-5', 'EC-Earth3-ESM-1', 'GFDL-ESM2M', ...]

mp = load_mapping("GFDL-ESM2M")
on_gwl = resample_to_gwl(mp, my_annual_diagnostic)   # shared 0.02 °C grid
# on_native = relabel_to_gwl(mp, my_annual_diagnostic)  # model's own GWL axis
```

Full API guide: [docs/using_mappings.md](docs/using_mappings.md).

## Two transforms

| Function | Output axis | Use when |
|----------|-------------|----------|
| `resample_to_gwl` | shared 0–4 °C grid (0.02 °C steps) | stacking or comparing models at the same GWL |
| `relabel_to_gwl` | native per-model GWL (uneven, unbinned) | plotting one model without binning |

Both operate on **annual** data whose coordinate values are calendar years. Values are never extrapolated beyond each model's realised warming range.

## Bundled mappings

The published ramp-up ensemble (`esm-up2p0`, mapping version `v1`) ships inside the package. You do not need to download separate NetCDF files — `load_mapping(model)` resolves them automatically.

Each mapping file is a **coordinate product** (`year_of_gwl`, `gwl_axis`, baseline and provenance metadata), not remapped fields. Apply it to your own variable with the functions above.

To use a locally rebuilt mapping instead, pass `path=` to `load_mapping` or open the file with xarray directly.

## Repository layout

```
src/tipmip_gwl/          library (mapping algorithm, resample/relabel API, bundled data)
docs/                    user and maintainer guides
examples/                runnable tutorials
paper/                   reproduce paper figures and tables (maintainer / GMD)
scripts/                 HPC staging helpers; see scripts/README.md
mapping/                 local build output when regenerating mappings (optional)
```

## Documentation

| Guide | Audience |
|-------|----------|
| [docs/using_mappings.md](docs/using_mappings.md) | **Users** — resample, relabel, ensemble stacks |
| [docs/building_mappings.md](docs/building_mappings.md) | **Maintainers** — preprocess tas, build mappings, sync bundled data |
| [docs/gmstmon_pipeline.md](docs/gmstmon_pipeline.md) | **Maintainers** — tas → gmstmon preprocessing detail |
| [docs/paper_figures.md](docs/paper_figures.md) | **Paper reproduction** — `paper/build_all.py` and figure scripts |

## Reproducing paper figures

Paper figures and tables are built from staged TIPMIP data, not from the library alone. See [docs/paper_figures.md](docs/paper_figures.md).

## Examples

```bash
python examples/resample_diagnostic.py GFDL-ESM2M
python examples/synthetic_demo.py
```

## Citation

If you use these mappings or the resampling method in published work, cite the accompanying GMD paper (in preparation) and pin the package version (`tipmip_gwl.__version__`) and mapping version (`v1`).
