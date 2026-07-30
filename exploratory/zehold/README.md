# Zero-emission hold (exploratory)

**Not part of the v1 installable package or GMD paper.**

Characterisation of the TIPMIP zero-emission-hold legs (`esm-up2p0-gwl2p0`,
`gwl4p0`, NorESM `swl*p0`, UKESM TerraFIRMA names). These mappings ship only
the forward transform `gwl_axis(year)` — no `year_of_gwl`, no common GWL grid.
Use `tipmip_gwl.relabel_to_gwl`, not `resample_to_gwl`.

The v1 paper covers ramp-up and ramp-down only. Hysteresis figures use up vs
down on the GWL axis and do not need ZE mapping files.

## Build ZE mappings (local maintainer)

Requires `pip install -e .` from the repo root:

```bash
conda activate toad312
python exploratory/zehold/zehold.py \
  --ze-dir ~/data/tipmip/tas/esm-up2p0-gwl2p0/gmstmon \
  --picontrol-dir ~/data/tipmip/tas/esm-piControl/gmstmon \
  --outdir mapping/
```

ZE `.nc` files are **not** synced into `src/tipmip_gwl/data/mappings/`.

## Trajectory preview (QA figure, not for paper)

Stitches ramp-up + ZE-hold + ramp-down on a calendar axis when all three mapping
products exist under `mapping/`:

```bash
python exploratory/zehold/plot_trajectory.py --mapping-dir mapping
```

Output defaults to `exploratory/zehold/figures/up_down_trajectory_preview.png`.

## Tests

```bash
pytest exploratory/zehold/test_zehold.py
```
