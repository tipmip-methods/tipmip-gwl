"""
Worked example: apply a bundled mapping to a synthetic diagnostic.

Shows the operational use of :func:`tipmip_gwl.load_mapping` and
:func:`tipmip_gwl.resample_to_gwl` — turning a variable on calendar time into
one on the common GWL axis.

Run::

    python examples/resample_diagnostic.py
    python examples/resample_diagnostic.py GFDL-ESM2M
    python examples/resample_diagnostic.py mapping/gwlmap_GFDL-ESM2M_esm-up2p0_v1.nc

Three things this example deliberately demonstrates:

1. Alignment is by year *value*. The synthetic diagnostic below starts a few
   years after the ramp-up and ends a few years before it — ``resample_to_gwl``
   still lines it up correctly, because it joins on the ``year`` coordinate, not
   on array position.
2. NaN is real, not clamped. GWLs the model never reached, and GWLs whose year
   falls outside the diagnostic's own range, come back as NaN — never an
   extrapolated end value.
3. The resample interpolates the diagnostic linearly *in time* between annual
   values (``year_of_gwl`` lands on fractional years). For abrupt mid-year
   changes this smears the jump across the straddling GWL bin; see the note in
   ``resample_to_gwl``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import xarray as xr

from tipmip_gwl import load_mapping, list_models, resample_to_gwl
from tipmip_gwl.io import model_label


def _open_mapping(arg: str | None) -> xr.Dataset:
    if arg is None:
        models = list_models()
        if not models:
            raise SystemExit("no bundled mappings found; pass a model id or gwlmap path")
        return load_mapping(models[0])
    path = Path(arg)
    if path.is_file():
        with xr.open_dataset(path) as ds:
            return ds.load()
    return load_mapping(arg)


def main(model_or_path: str | None = None):
    mp = _open_mapping(model_or_path)
    model = model_label(dict(mp.attrs))
    ru_years = mp["year"].values

    # A stand-in annual diagnostic. NOTE the year range is intentionally offset
    # from the ramp-up (starts +5, ends -3) to exercise coordinate alignment.
    diag_years = np.arange(ru_years.min() + 5, ru_years.max() - 2)
    rng = np.random.default_rng(0)
    values = np.cumsum(rng.standard_normal(diag_years.size)) + 50.0
    diagnostic = xr.DataArray(
        values, dims="year", coords={"year": diag_years}, name="my_diagnostic"
    )

    on_gwl = resample_to_gwl(mp, diagnostic)

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
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if len(sys.argv) > 2:
        raise SystemExit(
            "usage: python examples/resample_diagnostic.py [MODEL_OR_GWLMAP_PATH]"
        )
    main(arg)
