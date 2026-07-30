"""
build.py
========
Build TIPMIP time<->GWL mapping NetCDF products (maintainer API).

End users load published files with :mod:`tipmip_gwl.product`. This module
builds new ``gwlmap_*.nc`` files from staged gmstmon inputs.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr

from . import baseline as bl
from . import mapping
from .ensemble import (
    MissingEnsembleDataError,
    require_discovered,
    resolve_model_list,
)
from .io import discover, load_gmsat_nc, read_attrs
from .mapping import gwl_grid, gwl_grid_rampdown
from .product import default_mappings_dir
from .product import DEFAULT_EXPERIMENT, NotMappable


def _git_revision() -> str:
    """Short git hash of the installed source, or '' if unavailable."""
    try:
        here = Path(__file__).resolve().parent
        out = subprocess.check_output(
            ["git", "-C", str(here), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def _package_version() -> str:
    try:
        from . import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return "unknown"


@dataclass
class RampUpLeg:
    """Result of the shared ramp-up mapping pipeline."""

    model: str
    mm: mapping.ModelMapping
    base: bl.Baseline
    branch: int | None
    branch_info: bl.BranchInfo
    warns: list[str]
    ru_attrs: dict
    pi_attrs: dict
    ru_years: np.ndarray
    ru_gmsat: np.ndarray
    pi_years: np.ndarray
    pi_gmsat: np.ndarray


def compute_rampup_leg(
    model,
    ru_path,
    pi_path,
    *,
    window: int = 31,
    detrend: bool = False,
    t_grid=None,
) -> RampUpLeg:
    """Run provenance, baseline, and mapping for one ramp-up model pair."""
    if pi_path is None:
        raise NotMappable("no piControl tas available")

    t_grid = (
        mapping.MappingConfig().T_grid if t_grid is None else np.asarray(t_grid, float)
    )
    warns: list[str] = []
    ru_attrs = read_attrs(ru_path)
    warns.extend(bl.provenance_warnings(ru_attrs))

    ru_years, ru_gmsat = load_gmsat_nc(ru_path)
    pi_years, pi_gmsat = load_gmsat_nc(pi_path)
    pi_attrs = read_attrs(pi_path)

    bi = bl.branch_year_from_attrs(ru_attrs)
    try:
        branch, branch_warns = bl.resolve_branch_year(bi, model, ru_years, pi_years)
    except ValueError as exc:
        raise NotMappable(str(exc)) from exc
    warns.extend(branch_warns)

    base = bl.compute_baseline(
        pi_years, pi_gmsat, branch, detrend=detrend, window=window,
    )
    cfg = mapping.MappingConfig(
        window=window, method="running_mean", detrend_pi=detrend, T_grid=t_grid
    )
    mm = mapping.map_model(
        model,
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch,
        cfg=cfg,
        pi_reference=base.reference,
    )
    return RampUpLeg(
        model=model,
        mm=mm,
        base=base,
        branch=branch,
        branch_info=bi,
        warns=warns,
        ru_attrs=ru_attrs,
        pi_attrs=pi_attrs,
        ru_years=ru_years,
        ru_gmsat=ru_gmsat,
        pi_years=pi_years,
        pi_gmsat=pi_gmsat,
    )

def build_mapping_dataset(
    model,
    ru_path,
    pi_path,
    *,
    window: int = 31,
    detrend: bool = False,
    t_grid=None,
    mapping_version: str = "v1",
) -> xr.Dataset:
    """Compute the full mapping for one model and return it as an xarray Dataset.

    Raises :class:`NotMappable` only when no piControl tas is available for the
    model at all -- that is the sole hard requirement. Everything else -- wrong
    ``experiment_id``, no parent declared, a parent declared but its branch year
    specifically undecodable, or a branch year outside the staged piControl
    span -- is recorded as a warning on the output dataset instead of blocking
    the model.
    """
    try:
        leg = compute_rampup_leg(
            model, ru_path, pi_path, window=window, detrend=detrend, t_grid=t_grid,
        )
    except NotMappable:
        raise

    mm = leg.mm
    base = leg.base
    branch = leg.branch
    warns = leg.warns
    ru_attrs = leg.ru_attrs
    pi_attrs = leg.pi_attrs
    ru_years = leg.ru_years
    t_grid = mm.T_grid
    anom = mm.anom
    T_axis = mm.T_axis
    T_pre = mm.T_pre
    year_of_gwl = mm.t_of_T
    rep = mm.diagnostics

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = _package_version()

    ds = xr.Dataset(
        data_vars={
            "year_of_gwl": (
                "gwl",
                year_of_gwl.astype("float64"),
                {
                    "long_name": "model year at which each global warming level was reached",
                    "units": "year",
                    "comment": "Inverse transform t(GWL) by monotone cubic (PCHIP) "
                    "interpolation; NaN beyond the model's realised range.",
                },
            ),
            "gwl_axis": (
                "year",
                T_axis.astype("float64"),
                {
                    "long_name": "monotone global warming level axis",
                    "units": "degC",
                    "comment": "Forward transform GWL(t): 31-yr centred running mean of "
                    "the anomaly, made non-decreasing by isotonic (PAVA) regression. "
                    "This is the axis that was inverted.",
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
                },
            ),
            "picontrol_drift": (
                (),
                np.float64(base.drift_degC_per_century),
                {
                    "long_name": "linear drift of the full piControl GMSAT",
                    "units": "degC/century",
                    "comment": "Quality flag; |drift| > 0.5 degC/century suggests "
                    "checking baseline choice or using --detrend-pi.",
                },
            ),
            "monotonization_max": (
                (),
                np.float64(rep["monotonization_max_degC"]),
                {
                    "long_name": "maximum adjustment made by the monotonicity step",
                    "units": "degC",
                    "comment": "max|smoothed - monotone|; near zero means the inversion "
                    "is well posed, larger values flag a plateau/reversal to inspect.",
                },
            ),
            "branch_year": (
                (),
                np.float64(branch) if branch is not None else np.float64("nan"),
                {
                    "long_name": "piControl calendar year the ramp-up branched from",
                    "units": "year",
                    "comment": "NaN when the branch year could not be decoded "
                    "(baseline_method ends in '_no_branch_year'); falls back to "
                    "the full piControl mean.",
                },
            ),
            "max_gwl_reached": (
                (),
                np.float64(np.nanmax(T_axis)),
                {
                    "long_name": "maximum global warming level reached on the monotone axis",
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
                ru_years.astype("int32"),
                {"long_name": "ramp-up model calendar year", "units": "year"},
            ),
        },
    )

    ds.attrs = {
        "Conventions": "CF-1.10",
        "title": f"TIPMIP time-to-GWL mapping for {model} (esm-up2p0)",
        "summary": "Coordinate transform between calendar time and global warming "
        "level (GWL) for the TIPMIP esm-up2p0 ramp-up leg, with the piControl "
        "baseline and mapping diagnostics. Apply the transform to your own "
        "diagnostic variables; no remapped variables are shipped.",
        "method": (
            "GWL(t) = 31-yr centred running mean of GMSAT anomaly (isotonic), "
            f"minus piControl reference ({base.method}). "
            "See baseline_method and tipmip-gwl documentation."
        ),
        "source_id": str(ru_attrs.get("source_id", model)),
        "model_id": str(model),
        "experiment_id": str(ru_attrs.get("experiment_id", "esm-up2p0")),
        "variant_label": str(ru_attrs.get("variant_label", "")),
        "grid_label": str(ru_attrs.get("grid_label", "")),
        "baseline_method": base.method,
        "baseline_n_years": int(base.n_years),
        "picontrol_detrended": "true" if detrend else "false",
        "rampup_start_year": int(ru_years.min()),
        "rampup_file": Path(ru_path).name,
        "picontrol_file": Path(pi_path).name,
        "rampup_tracking_id": str(ru_attrs.get("tracking_id", "")),
        "picontrol_tracking_id": str(pi_attrs.get("tracking_id", "")),
        "parent_source_id": str(ru_attrs.get("parent_source_id", "")),
        "parent_experiment_id": str(ru_attrs.get("parent_experiment_id", "")),
        "parent_variant_label": str(ru_attrs.get("parent_variant_label", "")),
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

def load_rampup_baseline(mapping_dir, model) -> tuple[float, str] | None:
    """Return ``(baseline_gmsat, baseline_method)`` from a ramp-up mapping product.

    Looks in ``mapping_dir`` for a ``gwlmap_*`` file whose ``model_id`` matches
    ``model`` and whose ``leg`` attribute is ``ramp-up``. Returns ``None`` when
    no ramp-up product is found (callers fall back to computing a baseline).
    """
    mapping_dir = Path(mapping_dir)
    for path in sorted(mapping_dir.glob("gwlmap_*.nc")):
        with xr.open_dataset(path) as ds:
            if str(ds.attrs.get("leg", "ramp-up")) != "ramp-up":
                continue
            mid = str(ds.attrs.get("model_id") or ds.attrs.get("source_id", ""))
            if mid != model:
                continue
            return float(ds["baseline_gmsat"].values), str(
                ds.attrs.get("baseline_method", "")
            )
    return None


def resolve_secondary_leg_baseline(
    mapping_dir,
    model,
    pi_years,
    pi_gmsat,
    *,
    warns: list[str] | None = None,
) -> bl.Baseline:
    """Baseline for ramp-down / ZE-hold legs: inherit ramp-up product when present."""
    rampup = load_rampup_baseline(mapping_dir, model) if mapping_dir else None
    if rampup is not None:
        ref, method = rampup
        drift = mapping.picontrol_drift(pi_years, pi_gmsat)
        finite = np.isfinite(pi_years) & np.isfinite(pi_gmsat)
        return bl.Baseline(
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
    if mapping_dir is not None and warns is not None:
        warns.append(
            "no ramp-up mapping found in mapping_dir; baseline computed "
            "from piControl (full mean)"
        )
    return bl.compute_baseline(pi_years, pi_gmsat, branch_year=None)

# Ramp-down common GWL grid (fixed published choice; see _grid_bounds_warnings).
DEFAULT_T_GRID_RAMP_DOWN = gwl_grid_rampdown()
# Backward-compatible alias used in tests and call sites.
DEFAULT_T_GRID = DEFAULT_T_GRID_RAMP_DOWN


def _t_grid_for_dn_experiment(experiment_id: str) -> np.ndarray:
    """Return the published ramp-down common grid (same for all branches)."""
    del experiment_id  # branch id kept for call-site compatibility
    return DEFAULT_T_GRID_RAMP_DOWN


def _t_grid_for_dn_dir(dn_dir) -> np.ndarray:
    """Return the published ramp-down common grid."""
    del dn_dir  # kept for call-site compatibility
    return DEFAULT_T_GRID_RAMP_DOWN


def _parent_chain_warnings(dn_attrs: dict) -> list[str]:
    """Non-fatal provenance notes for the ramp-down leg's parent chain."""
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
    """Flag when a model's realised GWL range exceeds the configured T_grid."""
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

def write_mapping(ds: xr.Dataset, outdir, filename: str | None = None) -> Path:
    """Write a mapping dataset to NetCDF, returning the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        mid = ds.attrs.get("model_id") or ds.attrs.get("source_id", "model")
        ver = ds.attrs.get("mapping_version", "v1")
        exp = ds.attrs.get("experiment_id", DEFAULT_EXPERIMENT)
        filename = f"gwlmap_{mid}_{exp}_{ver}.nc"
    path = outdir / filename
    ds.to_netcdf(path)
    return path

def write_products(
    up2p0_dir,
    picontrol_dir,
    outdir,
    *,
    window: int = 31,
    detrend: bool = False,
    mapping_version: str = "v1",
    models: list[str] | tuple[str, ...] | None = None,
):
    """Build and write ramp-up mappings for the included ensemble.

    Only models in :data:`~tipmip_gwl.ensemble.INCLUDED_MODELS` (or ``models``)
    are built; extra gmstmon files in the directories are ignored. Raises
    :class:`~tipmip_gwl.ensemble.MissingEnsembleDataError` if any listed model
    lacks ramp-up or piControl gmstmon, or if mapping fails.

    Returns ``(written, skipped)`` where ``skipped`` is always empty.
    """
    model_list = resolve_model_list(models)
    ru_files = discover(up2p0_dir)
    pi_files = discover(picontrol_dir)
    require_discovered(model_list, ru_files, label="ramp-up")
    require_discovered(model_list, pi_files, label="piControl")

    written: list[tuple[str, Path]] = []
    for model in model_list:
        try:
            ds = build_mapping_dataset(
                model,
                ru_files[model],
                pi_files[model],
                window=window,
                detrend=detrend,
                mapping_version=mapping_version,
            )
        except NotMappable as exc:
            raise MissingEnsembleDataError(f"Cannot map {model}: {exc}") from exc
        path = write_mapping(ds, outdir)
        written.append((model, path))

    return written, []


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
    """Compute the ramp-down mapping for one model and return it as a Dataset."""
    t_grid = DEFAULT_T_GRID if t_grid is None else np.asarray(t_grid, float)

    dn_attrs = read_attrs(dn_path)
    warns = _parent_chain_warnings(dn_attrs)

    if pi_path is None:
        raise NotMappable("no piControl tas available")

    dn_years, dn_gmsat = load_gmsat_nc(dn_path)
    pi_years, pi_gmsat = load_gmsat_nc(pi_path)
    pi_attrs = read_attrs(pi_path)

    base = resolve_secondary_leg_baseline(
        mapping_dir, model, pi_years, pi_gmsat, warns=warns
    )

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


write_rampdown_mapping = write_mapping


def write_rampdown_products(
    dn_dir,
    picontrol_dir,
    outdir,
    *,
    window: int = 31,
    t_grid=None,
    mapping_version: str = "v1",
    models: list[str] | tuple[str, ...] | None = None,
):
    """Build and write ramp-down mappings for the included ensemble.

    Same ensemble filtering and strict missing-data checks as
    :func:`write_products`.
    """
    model_list = resolve_model_list(models)
    dn_files = discover(dn_dir)
    pi_files = discover(picontrol_dir)
    require_discovered(model_list, dn_files, label="ramp-down")
    require_discovered(model_list, pi_files, label="piControl")

    written: list[tuple[str, Path]] = []
    grid = _t_grid_for_dn_dir(dn_dir) if t_grid is None else np.asarray(t_grid, float)

    for model in model_list:
        try:
            ds = build_rampdown_mapping_dataset(
                model,
                dn_files[model],
                pi_files[model],
                window=window,
                t_grid=grid,
                mapping_version=mapping_version,
                mapping_dir=outdir,
            )
        except NotMappable as exc:
            raise MissingEnsembleDataError(f"Cannot map {model}: {exc}") from exc
        path = write_mapping(ds, outdir)
        written.append((model, path))

    return written, []


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build per-model TIPMIP time->GWL mapping NetCDF products."
    )
    parser.add_argument(
        "--leg",
        choices=("ramp-up", "ramp-down"),
        default="ramp-up",
        help="protocol leg to build (default ramp-up)",
    )
    parser.add_argument(
        "--up2p0-dir",
        help="ramp-up (esm-up2p0) gmstmon directory (required for ramp-up)",
    )
    parser.add_argument(
        "--dn-dir",
        help="ramp-down gmstmon directory (required for ramp-down)",
    )
    parser.add_argument("--picontrol-dir", required=True, help="piControl gmstmon directory")
    parser.add_argument("--outdir", default=str(default_mappings_dir()))
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--detrend-pi", action="store_true", help="ramp-up only")
    parser.add_argument("--mapping-version", default="v1")
    args = parser.parse_args(argv)

    if args.leg == "ramp-up":
        if not args.up2p0_dir:
            parser.error("--up2p0-dir is required for ramp-up")
        written, _skipped = write_products(
            args.up2p0_dir,
            args.picontrol_dir,
            args.outdir,
            window=args.window,
            detrend=args.detrend_pi,
            mapping_version=args.mapping_version,
        )
    else:
        if not args.dn_dir:
            parser.error("--dn-dir is required for ramp-down")
        written, _skipped = write_rampdown_products(
            args.dn_dir,
            args.picontrol_dir,
            args.outdir,
            window=args.window,
            mapping_version=args.mapping_version,
        )
    for model, path in written:
        print(f"wrote {model:16s} -> {path}")
    print(f"\n{len(written)} written")


def main_rampdown(argv=None):
    """Backward-compatible entry point for ramp-down builds."""
    argv = list(argv) if argv is not None else sys.argv[1:]
    return main(["--leg", "ramp-down", *argv])


if __name__ == "__main__":
    main()
