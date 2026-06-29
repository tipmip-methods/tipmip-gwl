# GWL mapping products (v1)

Coordinate products (`gwlmap_*_v1.nc`) for the included Tier-1 TIPMIP ensemble.
Each file maps calendar time ↔ global warming level for one model and experiment leg.

**27 files** (9 models × 3 legs):

- 9 × ramp-up (`esm-up2p0`)
- 9 × ramp-down from 2 °C hold
- 9 × ramp-down from 4 °C hold

Loaded by default via `load_mapping()`; rebuilt with `tipmip-gwl-build` or
`paper/build_all.py`. Override location: `export TIPMIP_GWL_MAPPINGS=/path/to/dir`.

Built from TIPMIP tas → gmstmon → `tipmip_gwl.build`. Algorithm and model list:
see the GMD paper and `src/tipmip_gwl/`.
