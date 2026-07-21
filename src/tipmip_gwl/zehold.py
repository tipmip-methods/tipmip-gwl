"""
zehold.py
=========
Per-model mapping product for the zero-emission-hold ("ZE") leg -- the
plateau between the ramp-up and ramp-down legs, held at a nominal target GWL
(``esm-up2p0-gwl2p0``, ``esm-up2p0-gwl4p0``, and model-specific variants such
as NorESM2-LM's ``esm-up2p0-swl2p0``/``swl4p0`` or UKESM's TerraFIRMA
``ZE-Up-2p0``/``ZE-Up-4p0``).

This is a genuinely different product from ``product.py``/``rampdown.py``,
not a third copy of the same schema:

* No monotonicity is enforced. Realised GWL during the hold can wander --
  keep warming for a while (a "zero emissions commitment" effect) or start
  relaxing immediately -- and that wander IS the signal this leg exists to
  characterise. Forcing a monotone axis here would erase it.
* Because there's no monotone axis, there's no well-posed inverse t(GWL), so
  this product ships no ``year_of_gwl`` and no common ``gwl`` grid coordinate
  -- structurally, not just because it hasn't been built yet. Only the
  forward transform (``gwl_axis(year)``, possibly non-monotonic) is
  meaningful, which is exactly what :func:`tipmip_gwl.product.relabel_to_gwl`
  (not ``resample_to_gwl``) already expects -- it never required monotonicity.
* Smoothing is lighter by default (15yr, not 31yr): the ramp-up/down windows
  match the protocol's own 31-yr diagnostic window for a 100-600 year leg; on
  a 50-year hold, a 31-yr centred window spends most of the record in its own
  edge-shrunk regime (see :func:`tipmip_gwl.mapping.running_mean`), so a
  shorter window is a better fit. It is purely cosmetic either way, since
  nothing is inverted from this leg.
* This leg's immediate parent is usually the ramp-up run itself
  (``esm-up2p0``), not piControl -- unlike the ramp-down leg, whose parent is
  one leg further removed. That means ``branch_time_in_parent`` decodes
  directly against the ramp-up's own calendar for most models here, and is
  recorded as informational provenance (never used for the baseline, which
  inherits the ramp-up mapping product's baseline when available).

Dependencies: numpy, xarray, and the sibling :mod:`tipmip_gwl` modules.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
from pathlib import Path

import numpy as np
import xarray as xr

from . import baseline as bl
from . import mapping
from .io import discover, load_gmsat_nc, read_attrs
from .product import NotMappable, _git_revision, _package_version, resolve_secondary_leg_baseline

# 50-year holds spend most of a 31-yr centred window in the edge-shrunk regime
# (see mapping.running_mean); this is closer to the "mostly full window"
# regime while still resolving the shape of the wander. Cosmetic only -- no
# monotonization or inversion is ever applied to this leg.
DEFAULT_WINDOW = 15


def _parse_target_gwl(experiment_id: str) -> float:
    """Best-effort nominal stabilization target parsed from the experiment id.

    Handles the naming conventions seen across the staged models: 'gwl2p0'/
    'gwl4p0' (most models), 'swl2p0'/'swl4p0' (NorESM2-LM), and 'ZE-Up-2p0'/
    'ZE-Up-4p0' (UKESM/TerraFIRMA). Checks the gwl/swl form first so it isn't
    fooled by the ramp-up experiment's own 'up2p0' tag (the '2p0' there is the
    2 degC/century *rate*, not a stabilization target, and would give the
    wrong answer for a gwl4p0 file if matched first).
    """
    m = re.search(r"(?:gwl|swl)(\d+)p(\d+)", experiment_id, re.IGNORECASE)
    if not m:
        m = re.search(r"up-?(\d+)p(\d+)", experiment_id, re.IGNORECASE)
    if not m:
        return float("nan")
    return float(f"{m.group(1)}.{m.group(2)}")


def _provenance_warnings(ze_attrs: dict) -> list[str]:
    """Non-fatal provenance notes specific to the ZE-hold leg's parent chain."""
    warns: list[str] = []
    branch_method = str(ze_attrs.get("branch_method", "")).strip().lower()
    parent_experiment_id = str(ze_attrs.get("parent_experiment_id", "") or "")

    if branch_method == "no parent" and not parent_experiment_id:
        warns.append(
            "no parent run declared (branch_method='no parent' or missing "
            "parent_experiment_id); baseline computed from full piControl "
            "only, paired by filename"
        )
        return warns

    if parent_experiment_id and "up2p0" not in parent_experiment_id.lower():
        warns.append(
            f"immediate parent is {parent_experiment_id!r}, not esm-up2p0 "
            "(a known metadata quirk for at least one staged model); "
            "branch-time decoding against it is informational only"
        )

    bi = bl.branch_year_from_attrs(ze_attrs)
    if bi.year is None and parent_experiment_id:
        warns.append(
            f"parent branch time could not be decoded "
            f"({bi.note or 'missing branch_time_in_parent/parent_time_units'}); "
            "informational only, does not affect the baseline"
        )
    return warns


def build_ze_mapping_dataset(
    model,
    ze_path,
    pi_path,
    *,
    window: int = DEFAULT_WINDOW,
    mapping_version: str = "v1",
    mapping_dir=None,
) -> xr.Dataset:
    """Compute the ZE-hold mapping for one model and return it as a Dataset.

    Raises :class:`tipmip_gwl.product.NotMappable` only when no piControl tas
    is available -- the same sole hard requirement as the other two legs.
    Unlike them, no monotone axis is built and no ``year_of_gwl``/common
    ``gwl`` grid is shipped: see the module docstring for why that's a
    structural difference, not an omission.
    """
    ze_attrs = read_attrs(ze_path)
    warns = _provenance_warnings(ze_attrs)

    if pi_path is None:
        raise NotMappable("no piControl tas available")

    ze_years, ze_gmsat = load_gmsat_nc(ze_path)
    pi_years, pi_gmsat = load_gmsat_nc(pi_path)
    pi_attrs = read_attrs(pi_path)

    base = resolve_secondary_leg_baseline(
        mapping_dir, model, pi_years, pi_gmsat, warns=warns
    )
    anom = mapping.to_anomaly(ze_years, ze_gmsat, base.reference)
    smoothed = mapping.running_mean(ze_years, anom, window)

    bi = bl.branch_year_from_attrs(ze_attrs)
    branch_year_in_parent = float(bi.year) if bi.year is not None else float("nan")

    experiment_id = str(ze_attrs.get("experiment_id", ""))
    target_gwl = _parse_target_gwl(experiment_id)
    if not np.isfinite(target_gwl):
        warns.append(
            f"could not parse a nominal target GWL from experiment_id "
            f"{experiment_id!r}; target_gwl will be NaN"
        )

    finite_idx = np.flatnonzero(np.isfinite(smoothed))
    if finite_idx.size == 0:
        raise NotMappable(f"no finite smoothed GWL values for {model}")
    gwl_at_hold_start = float(smoothed[finite_idx[0]])
    gwl_at_hold_end = float(smoothed[finite_idx[-1]])
    gwl_min = float(np.nanmin(smoothed))
    gwl_max = float(np.nanmax(smoothed))
    net_drift = gwl_at_hold_end - gwl_at_hold_start

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = _package_version()

    ds = xr.Dataset(
        data_vars={
            "gwl_axis": (
                "year",
                smoothed.astype("float64"),
                {
                    "long_name": f"{window}-yr centred running mean of the GMSAT "
                    "anomaly during the zero-emission hold",
                    "units": "degC",
                    "comment": "Forward transform only -- NOT made monotone. This "
                    "leg's trajectory can wander, and that wander is the signal "
                    "(zero-emissions-commitment behaviour), not noise to correct. "
                    "No inverse (year_of_gwl) exists for this leg; use "
                    "relabel_to_gwl (not resample_to_gwl) to plot a diagnostic "
                    "against this axis.",
                },
            ),
            "gmsat_anomaly": (
                "year",
                anom.astype("float64"),
                {
                    "long_name": "annual-mean GMSAT anomaly relative to piControl baseline",
                    "units": "degC",
                    "comment": "Unsmoothed days-in-month weighted annual mean minus the "
                    "scalar baseline.",
                },
            ),
            "baseline_gmsat": (
                (),
                np.float64(base.reference),
                {
                    "long_name": "piControl reference GMSAT (anomaly zero point)",
                    "units": "K",
                    "comment": "Same full-piControl-mean baseline convention as the "
                    "other two legs' mapping files for this model; should match them.",
                },
            ),
            "picontrol_drift": (
                (),
                np.float64(base.drift_degC_per_century),
                {
                    "long_name": "linear drift of the full piControl GMSAT",
                    "units": "degC/century",
                },
            ),
            "target_gwl": (
                (),
                np.float64(target_gwl),
                {
                    "long_name": "nominal stabilization target parsed from the "
                    "experiment id",
                    "units": "degC",
                },
            ),
            "gwl_at_hold_start": (
                (),
                np.float64(gwl_at_hold_start),
                {
                    "long_name": "smoothed realised GWL at the start of the staged "
                    "hold file",
                    "units": "degC",
                    "comment": "May differ from target_gwl by several tenths of a "
                    "degree; this is the model's own realised value, not the "
                    "nominal label.",
                },
            ),
            "gwl_at_hold_end": (
                (),
                np.float64(gwl_at_hold_end),
                {"long_name": "smoothed realised GWL at the end of the staged hold file",
                 "units": "degC"},
            ),
            "gwl_min_during_hold": (
                (), np.float64(gwl_min),
                {"long_name": "coldest smoothed GWL reached during the hold", "units": "degC"},
            ),
            "gwl_max_during_hold": (
                (), np.float64(gwl_max),
                {"long_name": "warmest smoothed GWL reached during the hold", "units": "degC"},
            ),
            "net_drift": (
                (),
                np.float64(net_drift),
                {
                    "long_name": "gwl_at_hold_end minus gwl_at_hold_start",
                    "units": "degC",
                    "comment": "Signed: positive means continued warming over the "
                    "hold (recalcitrant warming / zero-emissions commitment), "
                    "negative means net relaxation. The headline number for this leg.",
                },
            ),
            "branch_year_in_parent": (
                (),
                np.float64(branch_year_in_parent),
                {
                    "long_name": "decoded branch_time_in_parent, in the immediate "
                    "parent's own calendar",
                    "units": "year",
                    "comment": "For most staged models the parent is esm-up2p0 "
                    "itself, so this lands on the ramp-up's own calendar; "
                    "informational only, NaN when undecodable or no parent "
                    "declared. Not used for the baseline.",
                },
            ),
        },
        coords={
            "year": (
                "year",
                ze_years.astype("int32"),
                {"long_name": "zero-emission-hold model calendar year", "units": "year"},
            ),
        },
    )

    ds.attrs = {
        "Conventions": "CF-1.10",
        "title": f"TIPMIP GWL-hold characterisation for {model} (zero-emission hold)",
        "summary": "Realised GWL trajectory during a TIPMIP zero-emission-hold "
        "leg, referenced to the same piControl baseline as the ramp-up/ramp-down "
        "legs. Not an invertible coordinate transform -- see 'leg' and "
        "'hysteresis_note'. Apply gwl_axis via relabel_to_gwl to plot a "
        "diagnostic variable against it; no remapped variables are shipped.",
        "leg": "ze-hold",
        "hysteresis_note": "This leg's gwl_axis is not monotone by design and has "
        "no inverse -- do not use resample_to_gwl (a common-grid resample requires "
        "invertibility) or equate its GWL values with the ramp-up/ramp-down legs' "
        "at the 'same' GWL; path-dependence across all three legs is the point.",
        "method": f"gwl_axis(t) = {window}-yr centred running mean of GMSAT anomaly "
        f"(no monotonicity enforced), minus piControl reference ({base.method}).",
        "source_id": str(ze_attrs.get("source_id", model)),
        "model_id": str(model),
        "experiment_id": experiment_id,
        "variant_label": str(ze_attrs.get("variant_label", "")),
        "grid_label": str(ze_attrs.get("grid_label", "")),
        "baseline_method": base.method,
        "baseline_n_years": int(base.n_years),
        "smoothing_window_years": int(window),
        "hold_start_year": int(ze_years.min()),
        "hold_end_year": int(ze_years.max()),
        "hold_duration_years": int(ze_years.max() - ze_years.min()),
        "ze_file": Path(ze_path).name,
        "picontrol_file": Path(pi_path).name,
        "ze_tracking_id": str(ze_attrs.get("tracking_id", "")),
        "picontrol_tracking_id": str(pi_attrs.get("tracking_id", "")),
        "parent_source_id": str(ze_attrs.get("parent_source_id", "")),
        "parent_experiment_id": str(ze_attrs.get("parent_experiment_id", "")),
        "mapping_version": mapping_version,
        "code_package": "tipmip-gwl",
        "code_version": version,
        "git_revision": _git_revision(),
        "created": now,
        "history": f"{now}: created by tipmip-gwl {version}",
    }
    if warns:
        ds.attrs["mapping_warnings"] = "; ".join(warns)
    return ds


def write_ze_mapping(ds: xr.Dataset, outdir, filename: str | None = None) -> Path:
    """Write a ZE-hold mapping dataset to NetCDF, returning the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        mid = ds.attrs.get("model_id") or ds.attrs.get("source_id", "model")
        exp = ds.attrs.get("experiment_id", "esm-up2p0-gwl2p0")
        ver = ds.attrs.get("mapping_version", "v1")
        filename = f"gwlmap_{mid}_{exp}_{ver}.nc"
    path = outdir / filename
    ds.to_netcdf(path)
    return path


def write_ze_products(
    ze_dir,
    picontrol_dir,
    outdir,
    *,
    window: int = DEFAULT_WINDOW,
    mapping_version: str = "v1",
):
    """Build and write one ZE-hold mapping file per mappable model in ``ze_dir``.

    Returns ``(written, skipped)`` where ``written`` is a list of (model, path)
    and ``skipped`` is a list of (model, reason).
    """
    ze_files = discover(ze_dir)
    pi_files = discover(picontrol_dir)
    written, skipped = [], []

    for model in sorted(ze_files):
        try:
            ds = build_ze_mapping_dataset(
                model,
                ze_files[model],
                pi_files.get(model),
                window=window,
                mapping_version=mapping_version,
                mapping_dir=outdir,
            )
        except NotMappable as exc:
            skipped.append((model, str(exc)))
            continue
        path = write_ze_mapping(ds, outdir)
        written.append((model, path))

    return written, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the per-model TIPMIP zero-emission-hold GWL-characterisation product."
    )
    parser.add_argument(
        "--ze-dir", required=True,
        help="directory of ZE-hold (esm-up2p0-gwl*p0 / swl*p0 / ZE-Up-*) global-mean tas .nc files",
    )
    parser.add_argument(
        "--picontrol-dir", required=True,
        help="directory of piControl global-mean tas .nc files",
    )
    parser.add_argument(
        "--outdir", default="./mapping", help="output dir for mapping files (default ./mapping)"
    )
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW,
        help=f"smoothing window (years) for gwl_axis (default {DEFAULT_WINDOW})",
    )
    parser.add_argument("--mapping-version", default="v1")
    args = parser.parse_args(argv)

    written, skipped = write_ze_products(
        args.ze_dir,
        args.picontrol_dir,
        args.outdir,
        window=args.window,
        mapping_version=args.mapping_version,
    )
    for model, path in written:
        print(f"wrote {model:16s} -> {path}")
    for model, reason in skipped:
        print(f"skip  {model:16s} -- {reason}")
    print(f"\n{len(written)} written, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
