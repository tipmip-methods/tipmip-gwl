# Staged data and paper reproduction

Paper reproduction and mapping rebuilds expect **TIPMIP diagnostics on disk**.
This repository **does not distribute** raw tas, gmstmon, or mlotst files.

End users applying bundled mappings to their own diagnostics need **no staged data**.
See [using_mappings.md](using_mappings.md).

## Bundled vs staged

| Data | In repo? | Notes |
|------|----------|-------|
| GWL mapping products (`gwlmap_*_v1.nc`) | **Yes** (`mapping/`) | 27 files, 9 models × 3 legs |
| gmstmon, mlotst, sea-ice fields | **No** | Obtain via TIPMIP / institutional access |

## Directory layout

Default root: `~/data/tipmip/` (override via CLI flags on `build_all.py` and
`tipmip-gwl-build`).

```text
~/data/tipmip/
  tas/
    esm-up2p0/gmstmon/                    # one *_gmstmon.nc per included model
    esm-piControl/gmstmon/
    esm-up2p0-gwl2p0-50y-dn2p0/gmstmon/   # ramp-down 2 °C (optional)
    esm-up2p0-gwl4p0-50y-dn2p0/gmstmon/   # ramp-down 4 °C (optional)
  mlotst/
    esm-up2p0/                             # native *_annualmax.nc (remap figures)
    esm-up2p0-gwl4p0-50y-dn2p0/            # hysteresis figure (optional)
```

Included models and required gmstmon experiments:
`src/tipmip_gwl/ensemble.py` (`INCLUDED_MODELS`, `REQUIRED_GMSTMON_EXPERIMENTS`).

## Obtaining data

1. **TIPMIP protocol data** — request access through your institution (ESGF, DKRZ, etc.).
2. **Build gmstmon from tas** — [building_mappings.md](building_mappings.md) § preprocess.
3. **Bundled mappings only** — `pip install tipmip-gwl`; no TIPMIP staging required.

This repo documents **how to process** staged files, not **how to download** them from
a specific HPC account. Site-specific download and batch scripts are not shipped here.

## Reproduce paper figures

```bash
pip install -e ".[paper]"

python paper/build_all.py \
  --up2p0-dir ~/data/tipmip/tas/esm-up2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --mlotst-dir ~/data/tipmip/mlotst/esm-up2p0 \
  --dn-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0-50y-dn2p0/gmstmon \
  --dn4-dir ~/data/tipmip/tas/esm-up2p0-gwl4p0-50y-dn2p0/gmstmon
```

Rebuilds mapping products in ``mapping/`` when gmstmon is staged,
then runs each `paper/*.py` script.
Outputs: `paper/figures/`, `paper/tables/`. Ramp-down steps are skipped if dn gmstmon
is missing.

Mapping build detail: [building_mappings.md](building_mappings.md).  
Lighter tutorial: [examples/resample_diagnostic.ipynb](../examples/resample_diagnostic.ipynb).
