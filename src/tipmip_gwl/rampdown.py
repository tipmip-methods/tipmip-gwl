"""
rampdown.py
===========
Per-model TIPMIP time<->GWL mapping product for the *ramp-down* leg
(``esm-up2p0-gwl2p0-50y-dn2p0`` and model-specific variants such as
NorESM2-LM's ``esm-up2p0-swl2p0-50y-dn2p0`` or UKESM's TerraFIRMA
``Dn-8GtC-50y-2p0``).

Mirrors :mod:`tipmip_gwl.product`'s ramp-up pipeline, with two differences
that follow directly from this leg cooling instead of warming:

* The monotone axis is enforced *non-increasing*
  (``mapping.MappingConfig(direction="decreasing")``), and the common GWL
  grid spans the ramp-down leg's own realized range (models overshoot-cool
  to different depths, unlike the ramp-up leg where all clean models reach
  ~4 degC) rather than the ramp-up leg's 0-4 degC grid.
* This leg's immediate parent is the zero-emission hold run
  (``esm-up2p0-gwl2p0`` or similar), not piControl -- unlike the ramp-up leg,
  whose ``branch_time_in_parent`` decodes directly against the piControl
  calendar. Because the full-piControl-mean baseline never needs a branch
  year, this module does not attempt to decode/cross-check one against
  piControl for this leg; the decoded parent-chain metadata (if any) is
  recorded for provenance only, never used to compute the baseline or to
  gate mapping.

Do NOT use this leg's ``gwl_axis``/``year_of_gwl`` to equate a GWL reached on
the way down with the same GWL reached during the ramp-up leg: same GWL on
different legs is a different Earth-system state (see the scope notes in
:mod:`tipmip_gwl.mapping` and Fig. 4 of the paper draft).

Dependencies: numpy, xarray, and the sibling :mod:`tipmip_gwl` modules.
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

import numpy as np
import xarray as xr

from . import baseline as bl
from . import mapping
from .io import discover, load_gmsat_nc, read_attrs
from .product import load_rampup_baseline
from .mapping import gwl_grid
from .product import NotMappable, _git_revision, _package_version

# On the monotone axis (post-smoothing/PAVA), the eight staged ramp-down legs
# (esm-up2p0-gwl2p0-50y-dn2p0 and variants) reach a branch GWL between +1.73
# and +2.00 degC and cool to between -0.23 and -0.83 degC (coldest:
# EC-Earth3-ESM-1). This default grid gives every model ~0.7 degC of margin
# at both ends; values beyond a model's own realized range are still returned
# as NaN, never extrapolated (see mapping.invert_to_grid). It is a fixed,
# published choice, not recomputed per run -- see _grid_bounds_warnings for
# the self-check that flags when a new model or GWL target no longer fits.
DEFAULT_T_GRID = gwl_grid(gwl_min=-1.5, gwl_max=2.5)


def _parent_chain_warnings(dn_attrs: dict) -> list[str]:
    """Non-fatal provenance notes specific to the ramp-down leg's parent chain.

    Unlike the ramp-up leg (whose parent is piControl), this leg's declared
    parent is normally the zero-emission hold run. That's expected and not
    warned about; what's flagged here is the same class of imperfect linkage
    the ramp-up leg already tolerates (no parent declared at all, or a parent
    declared whose branch time can't be decoded) plus an explicit note that
    the parent is a hold run rather than piControl, so a reader doesn't
    mistake the decoded date for a piControl-relative branch year.
    """
    warns: list[str] = []
    branch_method = str(dn_attrs.get("branch_method", "")).strip().lower()
    parent_experiment_id = str(dn_attrs.get("parent_experiment_id", "") or "")

    if branch_method == "no parent" and not parent_experiment_id:
        warns.append(
            "no parent run declared (branch_method='no parent' or missing "
            "parent_experiment_id); baseline computed from full piControl "
            "only, paired by filename"
        )
        return warns

    if parent_experiment_id and "picontrol" not in parent_experiment_id.lower():
        warns.append(
            f"immediate parent is {parent_experiment_id!r} (the zero-emission "
            "hold run), not piControl; branch-time decoding against it is "
            "informational only and is not used for the baseline"
        )

    bi = bl.branch_year_from_attrs(dn_attrs)
    if bi.year is None and parent_experiment_id:
        warns.append(
            f"parent branch time could not be decoded "
            f"({bi.note or 'missing branch_time_in_parent/parent_time_units'}); "
            "informational only, does not affect the baseline"
        )
    return warns


def _grid_bounds_warnings(model: str, T_axis: np.ndarray, t_grid: np.ndarray) -> list[str]:
    """Flag when a model's realized GWL range exceeds the configured T_grid.

    DEFAULT_T_GRID is a fixed, published choice (see its module comment) --
    deliberately not recomputed from the data on every run, since a common
    grid that silently shifts between runs would break the "one canonical,
    versioned realisation" the paper commits to. Instead, each build checks
    itself against the configured bounds and warns loudly when a model no
    longer fits, so adding a new model (or a colder-reaching stabilization
    level, e.g. gwl4p0) surfaces the need to widen the grid immediately
    rather than silently dropping that model's coldest years from the
    common-grid product.
    """
    warns: list[str] = []
    lo, hi = float(np.min(t_grid)), float(np.max(t_grid))
    axis_lo, axis_hi = float(np.nanmin(T_axis)), float(np.nanmax(T_axis))
    if axis_lo < lo:
        warns.append(
            f"realised GWL reaches {axis_lo:.3f} degC, below the configured "
            f"T_grid minimum ({lo:.3f}); this model's coldest years are absent "
            "from the common-grid product -- widen gwl_min"
        )
    if axis_hi > hi:
        warns.append(
            f"realised GWL reaches {axis_hi:.3f} degC, above the configured "
            f"T_grid maximum ({hi:.3f}); this model's warmest years at branch "
            "are absent from the common-grid product -- widen gwl_max"
        )
    return warns


def build_rampdown_mapping_dataset(
    model,
    dn_path,
    pi_path,
    *,
    window: int = 31,
    t_grid=None,
    mapping_version: str = "v1",
    mapping_dir=None,
) -> xr.Dataset:
    """Compute the ramp-down mapping for one model and return it as a Dataset.

    Raises :class:`tipmip_gwl.product.NotMappable` only when no piControl tas
    is available for the model -- the same sole hard requirement as the
    ramp-up pipeline. Imperfect parent-chain metadata (this leg's normal
    case, since its parent is the hold run rather than piControl) is recorded
    as a warning, never blocking.
    """
    t_grid = DEFAULT_T_GRID if t_grid is None else np.asarray(t_grid, float)

    dn_attrs = read_attrs(dn_path)
    warns = _parent_chain_warnings(dn_attrs)

    if pi_path is None:
        raise NotMappable("no piControl tas available")

    dn_years, dn_gmsat = load_gmsat_nc(dn_path)
    pi_years, pi_gmsat = load_gmsat_nc(pi_path)
    pi_attrs = read_attrs(pi_path)

    rampup = load_rampup_baseline(mapping_dir, model) if mapping_dir else None
    if rampup is not None:
        ref, method = rampup
        drift = mapping.picontrol_drift(pi_years, pi_gmsat)
        finite = np.isfinite(pi_years) & np.isfinite(pi_gmsat)
        base = bl.Baseline(
            reference=ref,
            method=method,
            n_years=int(finite.sum()),
            span=(
                (float(pi_years[finite].min()), float(pi_years[finite].max()))
                if finite.any()
                else (np.nan, np.nan)
            ),
            drift_degC_per_century=drift["drift_degC_per_century"],
            detrended=False,
        )
    else:
        if mapping_dir is not None:
            warns.append(
                "no ramp-up mapping found in mapping_dir; baseline computed "
                "from piControl (full mean)"
            )
        base = bl.compute_baseline(pi_years, pi_gmsat, branch_year=None)

    cfg = mapping.MappingConfig(
        window=window,
        method="running_mean",
        detrend_pi=False,
        T_grid=t_grid,
        direction="decreasing",
    )
    mm = mapping.map_model(
        model,
        dn_years,
        dn_gmsat,
        pi_years,
        pi_gmsat,
        branch_year=None,
        cfg=cfg,
        pi_reference=base.reference,
    )
    anom = mm.anom
    T_axis = mm.T_axis
    T_pre = mm.T_pre
    year_of_gwl = mm.t_of_T
    rep = mm.diagnostics

    warns.extend(_grid_bounds_warnings(model, T_axis, t_grid))

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = _package_version()
    experiment_id = str(dn_attrs.get("experiment_id", "esm-up2p0-gwl2p0-50y-dn2p0"))

    ds = xr.Dataset(
        data_vars={
            "year_of_gwl": (
                "gwl",
                year_of_gwl.astype("float64"),
                {
                    "long_name": "model year at which each global warming level "
                    "was reached on the way down",
                    "units": "year",
                    "comment": "Inverse transform t(GWL) by monotone cubic (PCHIP) "
                    "interpolation on the non-increasing axis; NaN beyond the "
                    "model's realised range. Do not compare against the ramp-up "
                    "leg's year_of_gwl at the same GWL -- different Earth-system "
                    "state, see the dataset's 'leg' and 'hysteresis_note' attrs.",
                },
            ),
            "gwl_axis": (
                "year",
                T_axis.astype("float64"),
                {
                    "long_name": "monotone (non-increasing) global warming level axis",
                    "units": "degC",
                    "comment": "Forward transform GWL(t): 31-yr centred running mean "
                    "of the anomaly, made non-increasing by mirrored isotonic (PAVA) "
                    "regression. This is the axis that was inverted.",
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
            "gmsat_anomaly_smoothed": (
                "year",
                T_pre.astype("float64"),
                {
                    "long_name": "31-yr centred running mean of the GMSAT anomaly",
                    "units": "degC",
                    "comment": "Smoothed anomaly before the monotonicity step.",
                },
            ),
            "baseline_gmsat": (
                (),
                np.float64(base.reference),
                {
                    "long_name": "piControl reference GMSAT (anomaly zero point)",
                    "units": "K",
                    "comment": "Same baseline_gmsat as the ramp-up leg's mapping "
                    "file for this model when available; should match it.",
                },
            ),
            "picontrol_drift": (
                (),
                np.float64(base.drift_degC_per_century),
                {
                    "long_name": "linear drift of the full piControl GMSAT",
                    "units": "degC/century",
                    "comment": "Quality flag; |drift| > 0.5 degC/century suggests "
                    "checking baseline choice.",
                },
            ),
            "monotonization_max": (
                (),
                np.float64(rep["monotonization_max_degC"]),
                {
                    "long_name": "maximum adjustment made by the monotonicity step",
                    "units": "degC",
                    "comment": "max|smoothed - monotone|; near zero means the inversion "
                    "is well posed, larger values flag a plateau/reversal (e.g. a "
                    "delayed peak after the branch) to inspect.",
                },
            ),
            "gwl_at_branch": (
                (),
                np.float64(T_axis[0]) if len(T_axis) else np.float64("nan"),
                {
                    "long_name": "realised global warming level at the start of the "
                    "staged ramp-down file (after the zero-emission hold)",
                    "units": "degC",
                    "comment": "May differ from the nominal protocol target (e.g. "
                    "'2.0') by several tenths of a degree; this is the model's own "
                    "realised value on the monotone axis, not the nominal label.",
                },
            ),
            "min_gwl_reached": (
                (),
                np.float64(np.nanmin(T_axis)),
                {
                    "long_name": "coldest global warming level reached on the monotone axis",
                    "units": "degC",
                },
            ),
        },
        coords={
            "gwl": (
                "gwl",
                t_grid.astype("float64"),
                {
                    "long_name": "global warming level (GMSAT anomaly above piControl baseline)",
                    "units": "degC",
                    "axis": "X",
                },
            ),
            "year": (
                "year",
                dn_years.astype("int32"),
                {"long_name": "ramp-down model calendar year", "units": "year"},
            ),
        },
    )

    ds.attrs = {
        "Conventions": "CF-1.10",
        "title": f"TIPMIP time-to-GWL mapping for {model} (ramp-down leg)",
        "summary": "Coordinate transform between calendar time and global warming "
        "level (GWL) for the TIPMIP ramp-down leg, with the piControl baseline "
        "and mapping diagnostics. Apply the transform to your own diagnostic "
        "variables; no remapped variables are shipped.",
        "leg": "ramp-down",
        "hysteresis_note": "Do not equate a GWL reached on this leg with the same "
        "GWL reached on the ramp-up leg for the same model -- they are different "
        "Earth-system states by design; that path-dependence is the point of "
        "comparing the two legs, not an artifact to reconcile.",
        "method": (
            "GWL(t) = 31-yr centred running mean of GMSAT anomaly, made "
            f"non-increasing by mirrored isotonic regression, minus piControl "
            f"reference ({base.method}). See tipmip-gwl documentation."
        ),
        "source_id": str(dn_attrs.get("source_id", model)),
        "model_id": str(model),
        "experiment_id": experiment_id,
        "variant_label": str(dn_attrs.get("variant_label", "")),
        "grid_label": str(dn_attrs.get("grid_label", "")),
        "baseline_method": base.method,
        "baseline_n_years": int(base.n_years),
        "rampdown_start_year": int(dn_years.min()),
        "rampdown_file": Path(dn_path).name,
        "picontrol_file": Path(pi_path).name,
        "rampdown_tracking_id": str(dn_attrs.get("tracking_id", "")),
        "picontrol_tracking_id": str(pi_attrs.get("tracking_id", "")),
        "parent_source_id": str(dn_attrs.get("parent_source_id", "")),
        "parent_experiment_id": str(dn_attrs.get("parent_experiment_id", "")),
        "parent_variant_label": str(dn_attrs.get("parent_variant_label", "")),
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


def write_rampdown_mapping(ds: xr.Dataset, outdir, filename: str | None = None) -> Path:
    """Write a ramp-down mapping dataset to NetCDF, returning the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        mid = ds.attrs.get("model_id") or ds.attrs.get("source_id", "model")
        exp = ds.attrs.get("experiment_id", "esm-up2p0-gwl2p0-50y-dn2p0")
        ver = ds.attrs.get("mapping_version", "v1")
        filename = f"gwlmap_{mid}_{exp}_{ver}.nc"
    path = outdir / filename
    ds.to_netcdf(path)
    return path


def write_rampdown_products(
    dn_dir,
    picontrol_dir,
    outdir,
    *,
    window: int = 31,
    t_grid=None,
    mapping_version: str = "v1",
):
    """Build and write one ramp-down mapping file per mappable model in ``dn_dir``.

    Returns ``(written, skipped)`` where ``written`` is a list of (model, path)
    and ``skipped`` is a list of (model, reason).
    """
    dn_files = discover(dn_dir)
    pi_files = discover(picontrol_dir)
    written, skipped = [], []

    for model in sorted(dn_files):
        try:
            ds = build_rampdown_mapping_dataset(
                model,
                dn_files[model],
                pi_files.get(model),
                window=window,
                t_grid=t_grid,
                mapping_version=mapping_version,
                mapping_dir=outdir,
            )
        except NotMappable as exc:
            skipped.append((model, str(exc)))
            continue
        path = write_rampdown_mapping(ds, outdir)
        written.append((model, path))

    return written, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the per-model TIPMIP ramp-down time->GWL mapping NetCDF product."
    )
    parser.add_argument(
        "--dn-dir", required=True,
        help="directory of ramp-down (esm-up2p0-*-dn2p0) global-mean tas .nc files",
    )
    parser.add_argument(
        "--picontrol-dir", required=True,
        help="directory of piControl global-mean tas .nc files",
    )
    parser.add_argument(
        "--outdir", default="./mapping", help="output dir for mapping files (default ./mapping)"
    )
    parser.add_argument(
        "--window", type=int, default=31,
        help="smoothing window (years) for the GWL axis",
    )
    parser.add_argument("--mapping-version", default="v1")
    args = parser.parse_args(argv)

    written, skipped = write_rampdown_products(
        args.dn_dir,
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
