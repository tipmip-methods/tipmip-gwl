"""
product.py
==========
Build the canonical data product: one NetCDF file per TIPMIP ESM that holds the
time<->GWL transform plus the baseline, provenance, and mapping diagnostics.

The file is a *coordinate* product, not a data job: it ships the transform
(``year_of_gwl`` = t(GWL) on the common 0-4 degC grid, and ``gwl_axis`` =
forward GWL(t)) so downstream users apply it to their own diagnostic variables.
No remapped variables are stored.

Each file records enough to make a downstream analysis reproducible and pinnable:
input ``tracking_id``s, the parent run, the baseline method and drift, the
monotonisation adjustment, the code version, and a mapping version.

Dependencies: numpy, xarray, and the sibling :mod:`tipmip_gwl` modules.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
from pathlib import Path

import numpy as np
import xarray as xr

from . import baseline as bl
from . import mapping
from .io import discover, load_gmsat_nc, read_attrs


class NotMappable(Exception):
    """Raised when a model cannot be mapped (bad provenance, missing or wrong
    piControl, undecodable branch year). The reason is the message."""


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

    Raises :class:`NotMappable` (rather than writing a misleading file) when the
    run fails provenance, has no usable piControl, or branches outside the
    available control span without being a genuine day-0 branch.
    """
    t_grid = (
        mapping.MappingConfig().T_grid if t_grid is None else np.asarray(t_grid, float)
    )

    ru_attrs = read_attrs(ru_path)
    ok, reason = bl.provenance_check(ru_attrs)
    if not ok:
        raise NotMappable(f"provenance: {reason}")
    if pi_path is None:
        raise NotMappable("no piControl tas available")

    ru_years, ru_gmsat = load_gmsat_nc(ru_path)
    pi_years, pi_gmsat = load_gmsat_nc(pi_path)
    pi_attrs = read_attrs(pi_path)

    bi = bl.branch_year_from_attrs(ru_attrs)
    known = bl.KNOWN_BRANCH_YEARS.get(model)
    branch = bi.year if bi.year is not None else known
    if branch is None:
        raise NotMappable("branch year could not be decoded from metadata")

    # A branch earlier than the start of the staged control means the control is
    # the wrong/incomplete run (e.g. NorESM branches at 1600, control starts
    # 1851). A genuine day-0 branch (branch_time_in_parent == 0) is fine and uses
    # a trailing window instead.
    if not bi.at_parent_start and not (pi_years.min() <= branch <= pi_years.max()):
        raise NotMappable(
            f"branch year {branch} outside piControl span "
            f"[{int(pi_years.min())}-{int(pi_years.max())}] (wrong or incomplete control)"
        )

    base = bl.compute_baseline(
        pi_years, pi_gmsat, branch, window=window, detrend=detrend,
        at_parent_start=bi.at_parent_start,
    )
    anom = mapping.to_anomaly(ru_years, ru_gmsat, base.reference)
    T_axis, T_pre = mapping.axis_variable(
        ru_years, anom, method="running_mean", window=window, return_intermediate=True
    )
    year_of_gwl = mapping.invert_to_grid(ru_years, T_axis, t_grid)
    rep = mapping.monotonicity_report(anom, T_pre, T_axis)

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
                np.float64(base.drift_full_degC_per_century),
                {
                    "long_name": "linear drift of the full piControl GMSAT",
                    "units": "degC/century",
                    "comment": "Quality flag; |drift| > 0.5 means the baseline is "
                    "sensitive to which years the window covers.",
                },
            ),
            "picontrol_drift_window": (
                (),
                np.float64(base.drift_window_degC_per_century),
                {
                    "long_name": "linear drift of piControl GMSAT over the baseline window",
                    "units": "degC/century",
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
                np.int32(branch),
                {
                    "long_name": "piControl calendar year the ramp-up branched from",
                    "units": "year",
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
        "method": "GWL(t) = smoothed(GMSAT_rampup(t)) - mean(GMSAT_piControl over a "
        "31-yr window at the branch year). See the tipmip-gwl documentation.",
        "source_id": str(ru_attrs.get("source_id", model)),
        "experiment_id": str(ru_attrs.get("experiment_id", "esm-up2p0")),
        "variant_label": str(ru_attrs.get("variant_label", "")),
        "grid_label": str(ru_attrs.get("grid_label", "")),
        "baseline_method": base.method,
        "baseline_window_years": int(window),
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
    return ds


def write_mapping(ds: xr.Dataset, outdir, filename: str | None = None) -> Path:
    """Write a mapping dataset to NetCDF, returning the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        sid = ds.attrs.get("source_id", "model")
        ver = ds.attrs.get("mapping_version", "v1")
        filename = f"gwlmap_{sid}_esm-up2p0_{ver}.nc"
    path = outdir / filename
    ds.to_netcdf(path)
    return path


def remap_to_gwl(mapping_ds, data, year_dim="year"):
    """Remap a diagnostic from calendar time onto the common GWL grid.

    This is the operational use of a mapping file: it applies ``year_of_gwl``
    (the inverse transform t(GWL)) to your own variable, returning it indexed by
    ``gwl`` so models can be stacked on the shared axis.

    Parameters
    ----------
    mapping_ds : x.Dataset
        A mapping product (from :func:`build_mapping_dataset` or a published
        ``gwlmap_*.nc``). Only ``year_of_gwl`` and the ``gwl`` coord are used.
    data : x.DataArray or x.Dataset
        The diagnostic on an **annual** axis whose coordinate values are calendar
        years (named ``year_dim``). Alignment is by coordinate *value*, so the
        diagnostic need not start on the same year or have the same length as the
        ramp-up; non-overlapping years simply map to NaN.
    year_dim : str
        Name of the annual coordinate on ``data`` (default ``"year"``).

    Returns
    -------
    Same type as ``data``, with ``year_dim`` replaced by ``gwl``. Values are NaN
    wherever the model never reached that GWL (``year_of_gwl`` is NaN) or where
    the required year falls outside the diagnostic's own range -- never
    extrapolated.

    Notes
    -----
    ``year_of_gwl`` lands on *fractional* years (e.g. 2.0 degC at year 1964.3),
    so the diagnostic is linearly interpolated between its annual values. For a
    genuinely abrupt change occurring mid-year this smears the jump across the
    straddling GWL bin. That is unavoidable at annual resolution; if sub-annual
    timing matters for your analysis, supply a monthly diagnostic (the axis stays
    annual, but the interpolation has finer values to land on).
    """
    if year_dim not in getattr(data, "dims", {}):
        raise ValueError(
            f"data has no {year_dim!r} dimension; pass year_dim=... with the "
            f"name of its annual coordinate (dims: {tuple(getattr(data, 'dims', ()))})"
        )
    target = mapping_ds["year_of_gwl"]  # dim 'gwl', fractional years (with NaN)
    out = data.interp({year_dim: target})
    return out.drop_vars(year_dim, errors="ignore")


def write_products(
    up2p0_dir,
    picontrol_dir,
    outdir,
    *,
    window: int = 31,
    detrend: bool = False,
    mapping_version: str = "v1",
):
    """Build and write one mapping file per mappable model in ``up2p0_dir``.

    Returns ``(written, skipped)`` where ``written`` is a list of (model, path)
    and ``skipped`` is a list of (model, reason).
    """
    ru_files = discover(up2p0_dir)
    pi_files = discover(picontrol_dir)
    written, skipped = [], []

    for model in sorted(ru_files):
        try:
            ds = build_mapping_dataset(
                model,
                ru_files[model],
                pi_files.get(model),
                window=window,
                detrend=detrend,
                mapping_version=mapping_version,
            )
        except NotMappable as exc:
            skipped.append((model, str(exc)))
            continue
        path = write_mapping(ds, outdir)
        written.append((model, path))

    return written, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the per-model TIPMIP time->GWL mapping NetCDF product."
    )
    parser.add_argument(
        "--up2p0-dir", required=True,
        help="directory of ramp-up (esm-up2p0) global-mean tas .nc files",
    )
    parser.add_argument(
        "--picontrol-dir", required=True,
        help="directory of piControl global-mean tas .nc files",
    )
    parser.add_argument(
        "--outdir", default="./mapping", help="output dir for mapping files (default ./mapping)"
    )
    parser.add_argument("--window", type=int, default=31)
    parser.add_argument("--detrend-pi", action="store_true")
    parser.add_argument("--mapping-version", default="v1")
    args = parser.parse_args(argv)

    written, skipped = write_products(
        args.up2p0_dir,
        args.picontrol_dir,
        args.outdir,
        window=args.window,
        detrend=args.detrend_pi,
        mapping_version=args.mapping_version,
    )
    for model, path in written:
        print(f"wrote {model:16s} -> {path}")
    for model, reason in skipped:
        print(f"skip  {model:16s} -- {reason}")
    print(f"\n{len(written)} written, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
