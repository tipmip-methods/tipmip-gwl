# Reproducing paper figures and tables

For maintainers/reviewers with staged TIPMIP data. Users applying mappings to their
own diagnostics only need [using_mappings.md](using_mappings.md).

## One command

```bash
pip install -e ".[paper]"

python paper/build_all.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/data/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon
```

Rebuilds `mapping/` (when gmstmon is staged), then runs each `paper/*.py` script.
Outputs: `paper/figures/`, `paper/tables/`. Ramp-down steps are skipped if dn gmstmon
is missing. Paper scripts use the **bundled v1 ensemble** (8 models) even if local
`mapping/` contains trial models such as CESM2.

Individual scripts are runnable standalone — see module docstrings. Step order matches
`paper/build_all.py`.

## Staged data

| Data | Typical path |
|------|--------------|
| Ramp-up gmstmon | `tas/esm-up2p0/gmstmon/` |
| piControl gmstmon | `tas/esm-piControl/gmstmon/` |
| mlotst (up) | `mlotst/esm-up2p0/` |
| Ramp-down gmstmon (2 / 4 °C) | `tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/`, `...gwl4p0-50y-dn2p0/...` |
| mlotst (dn 4 °C) | `mlotst/esm-up2p0-gwl4p0-50y-dn2p0/` |

Preprocess: [gmstmon_pipeline.md](gmstmon_pipeline.md). Mapping build: [building_mappings.md](building_mappings.md).

Committed figures in the repo match a full rebuild on this layout. Bundled mappings under
`src/tipmip_gwl/data/mappings/` are the published snapshot; `build_all.py` writes to
`mapping/` for consistency with your staged tas.

Lighter tutorial (no full staging): [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).
