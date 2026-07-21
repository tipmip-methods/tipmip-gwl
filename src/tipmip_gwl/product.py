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

Downstream users load published files with :func:`load_mapping` (bundled in the
package) and apply :func:`resample_to_gwl` or :func:`relabel_to_gwl` to their
own diagnostics.

Dependencies: numpy, xarray, and the sibling :mod:`tipmip_gwl` modules.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
from pathlib import Path

import numpy as np
import xarray as xr

from . import baseline as bl
from . import mapping
from .mapping import gwl_grid
from .io import discover, load_gmsat_nc, read_attrs


class NotMappable(Exception):
    """Raised when a model cannot be mapped (e.g. no piControl tas on disk)."""


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

    Raises :class:`NotMappable` only when no piControl tas is available for the
    model at all -- that is the sole hard requirement. Everything else -- wrong
    ``experiment_id``, no parent declared, a parent declared but its branch year
    specifically undecodable, or a branch year outside the staged piControl
    span -- is recorded as a warning on the output dataset instead of blocking
    the model.
    """
    t_grid = (
        mapping.MappingConfig().T_grid if t_grid is None else np.asarray(t_grid, float)
    )

    warns: list[str] = []
    ru_attrs = read_attrs(ru_path)
    warns.extend(bl.provenance_warnings(ru_attrs))

    if pi_path is None:
        raise NotMappable("no piControl tas available")

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


def write_mapping(ds: xr.Dataset, outdir, filename: str | None = None) -> Path:
    """Write a mapping dataset to NetCDF, returning the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        mid = ds.attrs.get("model_id") or ds.attrs.get("source_id", "model")
        ver = ds.attrs.get("mapping_version", "v1")
        filename = f"gwlmap_{mid}_esm-up2p0_{ver}.nc"
    path = outdir / filename
    ds.to_netcdf(path)
    return path


DEFAULT_EXPERIMENT = "esm-up2p0"
DEFAULT_MAPPING_VERSION = "v1"

_FILENAME_RE = re.compile(
    r"^gwlmap_(?P<model>.+)_(?P<experiment>[^_]+(?:-[^_]+)*)_(?P<version>v\d+)\.nc$"
)


def bundled_mappings_dir() -> Path:
    """Directory containing ramp-up mapping files bundled in the wheel/sdist."""
    return Path(__file__).resolve().parent / "data" / "mappings"


def _parse_mapping_filename(path: Path) -> tuple[str, str, str] | None:
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None
    return m.group("model"), m.group("experiment"), m.group("version")


def list_models(
    *,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str = DEFAULT_EXPERIMENT,
    mapping_dir: Path | str | None = None,
) -> list[str]:
    """Return sorted model ids with a mapping file in ``mapping_dir``.

    Defaults to the bundled ramp-up ensemble shipped with the package.
    """
    root = Path(mapping_dir) if mapping_dir is not None else bundled_mappings_dir()
    models: list[str] = []
    for path in sorted(root.glob("gwlmap_*.nc")):
        parsed = _parse_mapping_filename(path)
        if parsed is None:
            continue
        model, exp, ver = parsed
        if exp == experiment and ver == version:
            models.append(model)
    return models


def bundled_mapping_path(
    model: str,
    *,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str = DEFAULT_EXPERIMENT,
) -> Path:
    """Path to a bundled mapping file (raises ``FileNotFoundError`` if absent)."""
    path = bundled_mappings_dir() / f"gwlmap_{model}_{experiment}_{version}.nc"
    if not path.is_file():
        available = ", ".join(list_models(version=version, experiment=experiment))
        raise FileNotFoundError(
            f"no bundled mapping for {model!r} ({experiment}, {version}); "
            f"available models: {available or '(none)'}"
        )
    return path


def load_mapping(
    model: str,
    *,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str = DEFAULT_EXPERIMENT,
    path: Path | str | None = None,
) -> xr.Dataset:
    """Load a ramp-up mapping product into memory.

    By default opens the copy bundled with the installed package. Pass ``path=``
    to use a custom ``gwlmap_*.nc`` (for example one you rebuilt locally).
    """
    src = Path(path) if path is not None else bundled_mapping_path(
        model, version=version, experiment=experiment
    )
    with xr.open_dataset(src) as ds:
        return ds.load()


def _year_of_gwl_target(
    mapping_ds: xr.Dataset,
    gwl_step: float = mapping.GWL_GRID_STEP,
    gwl_max: float = 4.0,
) -> xr.DataArray:
    """Fractional model year at each GWL on the requested grid (for ``resample_to_gwl``)."""
    grid = gwl_grid(gwl_step, gwl_max)
    src_gwl = np.asarray(mapping_ds["gwl"].values, dtype=float)
    src_years = np.asarray(mapping_ds["year_of_gwl"].values, dtype=float)
    finite = np.isfinite(src_years) & np.isfinite(src_gwl)
    if finite.sum() < 2:
        raise ValueError("mapping_ds['year_of_gwl'] has too few finite values")
    years = np.interp(
        grid, src_gwl[finite], src_years[finite], left=np.nan, right=np.nan
    )
    return xr.DataArray(years, dims=["gwl"], coords={"gwl": ("gwl", grid)})


def resample_to_gwl(
    mapping_ds,
    data,
    year_dim="year",
    *,
    gwl_step: float = mapping.GWL_GRID_STEP,
    gwl_max: float = 4.0,
):
    """Resample a diagnostic from calendar time onto the common GWL grid.

    This is the operational use of a mapping file: it applies ``year_of_gwl``
    (the inverse transform t(GWL)) to your own variable, returning it indexed by
    ``gwl`` so models can be stacked on the shared axis.

    Parameters
    ----------
    mapping_ds : x.Dataset
        A mapping product (from :func:`build_mapping_dataset` or a published
        ``gwlmap_*.nc``). ``year_of_gwl`` is interpolated onto the grid defined
        by ``gwl_step`` and ``gwl_max``.
    data : x.DataArray or x.Dataset
        The diagnostic on an **annual** axis whose coordinate values are calendar
        years (named ``year_dim``). Alignment is by coordinate *value*, so the
        diagnostic need not start on the same year or have the same length as the
        ramp-up; non-overlapping years simply map to NaN.
    year_dim : str
        Name of the annual coordinate on ``data`` (default ``"year"``).
    gwl_step : float
        GWL grid spacing in degC (default ``0.02``).
    gwl_max : float
        Upper end of the GWL grid in degC (default ``4.0``).

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
    target = _year_of_gwl_target(mapping_ds, gwl_step=gwl_step, gwl_max=gwl_max)
    out = data.interp({year_dim: target})
    return out.drop_vars(year_dim, errors="ignore")


def relabel_to_gwl(
    mapping_ds, data, year_dim="year", *, year_offset=0.0, new_dim="gwl"
):
    """Relabel a model's time axis with continuous GWL via the forward map.

    The *other* GWL transform. Where :func:`resample_to_gwl` resamples a diagnostic
    onto the shared 0-4 degC grid (binned, comparable across models), this keeps
    the data at its **native temporal resolution** and merely replaces the year
    coordinate with the warming level reached that year -- the forward transform
    ``gwl_axis(year)``. Each model ends up on its own GWL axis (uneven spacing,
    not shared), which is what you want for plotting a single model against GWL
    without losing resolution or smearing abrupt changes across bins.

    Parameters
    ----------
    mapping_ds : xarray.Dataset
        A mapping product. Only ``gwl_axis`` and its ``year`` coord are used.
    data : xarray.DataArray or xarray.Dataset
        Data on a time/year axis named ``year_dim``.
    year_dim : str
        Name of the time coordinate on ``data`` (default ``"year"``).
    year_offset : float
        Added to ``data[year_dim]`` before alignment, to turn a zero-based axis
        into calendar years (e.g. pass the mapping's ``rampup_start_year`` for an
        export whose time starts at 0). Default ``0.0`` (already calendar).
    new_dim : str or None
        Rename the relabelled dimension to this (default ``"gwl"``). Pass ``None``
        to keep ``year_dim`` as the dimension name -- useful when a downstream tool
        still expects the original axis name but with GWL values.

    Returns
    -------
    Same type as ``data``. Timesteps beyond the mapping's range (where
    ``gwl_axis`` is undefined) are dropped rather than extrapolated. Because
    ``gwl_axis`` is monotone non-decreasing, the relabelled axis stays sorted.
    """
    if year_dim not in getattr(data, "dims", {}):
        raise ValueError(
            f"data has no {year_dim!r} dimension; pass year_dim=... with the "
            f"name of its time coordinate (dims: {tuple(getattr(data, 'dims', ()))})"
        )
    years = np.asarray(data[year_dim].values, dtype=float) + float(year_offset)
    yr = np.asarray(mapping_ds["year"].values, dtype=float)
    ga = np.asarray(mapping_ds["gwl_axis"].values, dtype=float)
    finite = np.isfinite(ga)
    if finite.sum() < 2:
        raise ValueError("mapping_ds['gwl_axis'] has fewer than two finite values")
    gwl = np.interp(years, yr[finite], ga[finite], left=np.nan, right=np.nan)

    keep = np.isfinite(gwl)
    out = data.isel({year_dim: keep}).assign_coords({year_dim: gwl[keep]})
    out[year_dim].attrs.update(
        {"long_name": "global warming level", "units": "degC"}
    )
    if new_dim is not None and new_dim != year_dim:
        out = out.rename({year_dim: new_dim})
    return out


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
    parser.add_argument(
        "--window", type=int, default=31,
        help="smoothing window (years) for the GWL axis",
    )
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
