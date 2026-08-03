# Staged data and paper reproduction

Paper reproduction and mapping rebuilds expect **TIPMIP diagnostics on disk**.
This repository **does not distribute** raw tas, gmstmon, mlotst, or sea-ice fields.

End users applying bundled mappings to their own diagnostics need **no staged data**.
See [using_mappings.md](using_mappings.md).

**Figure/table commands, output list, and full data layout:**
[paper_reproduction.md](paper_reproduction.md).

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
  sivol/
    esm-up2p0/                             # sea-ice volume (hysteresis figure)
    esm-up2p0-gwl4p0-50y-dn2p0/
```

Included models and required gmstmon experiments:
`src/tipmip_gwl/ensemble.py` (`INCLUDED_MODELS`, `REQUIRED_GMSTMON_EXPERIMENTS`).

## Obtaining data

1. **TIPMIP protocol data** — request access through your institution (ESGF, DKRZ, etc.).
2. **Build gmstmon from tas** — [building_mappings.md](building_mappings.md) § preprocess.
3. **Bundled mappings only** — clone this repo and `pip install -e .`; no TIPMIP staging required.

This repo documents **how to process** staged files, not **how to download** them from
a specific HPC account. Site-specific download and batch scripts are not shipped here.

See [paper_reproduction.md](paper_reproduction.md) for the full rebuild command and
per-figure data requirements.
