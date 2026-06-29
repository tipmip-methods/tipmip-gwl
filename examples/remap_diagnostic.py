"""
Worked example: apply a mapping file to a diagnostic variable.

Shows the operational use of a ``gwlmap_*.nc`` product -- turning a variable on
calendar time into one on the common GWL axis with :func:`tipmip_gwl.remap_to_gwl`.

Run after building a product, e.g.::

    tipmip-gwl-build --up2p0-dir <dir> --picontrol-dir <dir> --outdir mapping/
    python examples/remap_diagnostic.py mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc

Three things this example deliberately demonstrates:

1. Alignment is by year *value*. The synthetic diagnostic below starts a few
   years after the ramp-up and ends a few years before it -- ``remap_to_gwl``
   still lines it up correctly, because it joins on the ``year`` coordinate, not
   on array position.
2. NaN is real, not clamped. GWLs the model never reached, and GWLs whose year
   falls outside the diagnostic's own range, come back as NaN -- never an
   extrapolated end value.
3. The remap interpolates the diagnostic linearly *in time* between annual
   values (``year_of_gwl`` lands on fractional years). For abrupt mid-year
   changes this smears the jump across the straddling GWL bin; see the note in
   ``remap_to_gwl``.
"""

import sys

import numpy as np
import xarray as xr

from tipmip_gwl import remap_to_gwl


def main(mapping_path):
    mp = xr.open_dataset(mapping_path)
    model = mp.attrs.get("source_id", "model")
    ru_years = mp["year"].values

    # A stand-in annual diagnostic. NOTE the year range is intentionally offset
    # from the ramp-up (starts +5, ends -3) to exercise coordinate alignment.
    diag_years = np.arange(ru_years.min() + 5, ru_years.max() - 2)
    rng = np.random.default_rng(0)
    values = np.cumsum(rng.standard_normal(diag_years.size)) + 50.0
    diagnostic = xr.DataArray(
        values, dims="year", coords={"year": diag_years}, name="my_diagnostic"
    )

    on_gwl = remap_to_gwl(mp, diagnostic)

    print(f"model: {model}")
    print(f"ramp-up years:    {int(ru_years.min())}-{int(ru_years.max())}")
    print(f"diagnostic years: {int(diag_years.min())}-{int(diag_years.max())} "
          "(offset on purpose)")
    print(f"max GWL reached:  {float(mp['max_gwl_reached']):.2f} degC\n")

    print(f"{'GWL':>5s} {'year_of_gwl':>12s} {'diagnostic(gwl)':>16s}")
    for g in np.arange(0.0, 4.0001, 0.5):
        yr = float(mp["year_of_gwl"].sel(gwl=g, method="nearest"))
        val = float(on_gwl.sel(gwl=g, method="nearest"))
        yr_s = f"{yr:12.1f}" if np.isfinite(yr) else f"{'nan':>12s}"
        val_s = f"{val:16.3f}" if np.isfinite(val) else f"{'nan':>16s}"
        print(f"{g:5.1f} {yr_s} {val_s}")

    n_nan = int(np.isnan(on_gwl.values).sum())
    print(f"\n{n_nan} of {on_gwl.size} GWL bins are NaN "
          "(unreached by the model, or outside the diagnostic's year range).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python examples/remap_diagnostic.py <gwlmap_*.nc>")
    main(sys.argv[1])
