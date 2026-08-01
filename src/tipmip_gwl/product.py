"""
product.py
==========
Load published TIPMIP time<->GWL mapping products and apply them to diagnostics.

Downstream users call :func:`load_mapping`, then :func:`resample_to_gwl` or
:func:`relabel_to_gwl`. Maintainers build new products with :mod:`tipmip_gwl.build`.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

import numpy as np
import xarray as xr

from . import mapping
from .ensemble import INCLUDED_MODELS
from .mapping import gwl_grid


class NotMappable(Exception):
    """Raised when a model cannot be mapped (e.g. no piControl tas on disk)."""


DEFAULT_EXPERIMENT = "esm-up2p0"
DEFAULT_MAPPING_VERSION = "v1"

MAPPINGS_DIR_NAME = "mapping"
MAPPINGS_ENV_VAR = "TIPMIP_GWL_MAPPINGS"
_WARNED_MISSING_MAPPINGS = False

LEG_RAMP_UP = "ramp-up"
LEG_RAMP_DOWN_2C = "ramp-down-2c"
LEG_RAMP_DOWN_4C = "ramp-down-4c"
_KNOWN_LEGS = (LEG_RAMP_UP, LEG_RAMP_DOWN_2C, LEG_RAMP_DOWN_4C)

_FILENAME_RE = re.compile(
    r"^gwlmap_(?P<model>.+)_(?P<experiment>[^_]+(?:-[^_]+)*)_(?P<version>v\d+)\.nc$"
)


def _normalize_leg(leg: str) -> str:
    key = leg.strip().lower().replace("_", "-")
    aliases = {
        "ramp-up": LEG_RAMP_UP,
        "up": LEG_RAMP_UP,
        "rampup": LEG_RAMP_UP,
        LEG_RAMP_DOWN_2C: LEG_RAMP_DOWN_2C,
        "ramp-down-2": LEG_RAMP_DOWN_2C,
        "dn-2c": LEG_RAMP_DOWN_2C,
        LEG_RAMP_DOWN_4C: LEG_RAMP_DOWN_4C,
        "ramp-down-4": LEG_RAMP_DOWN_4C,
        "dn-4c": LEG_RAMP_DOWN_4C,
    }
    try:
        return aliases[key]
    except KeyError as exc:
        raise ValueError(
            f"unknown leg {leg!r}; use one of {', '.join(_KNOWN_LEGS)}"
        ) from exc


def _experiment_matches_leg(experiment: str, leg: str) -> bool:
    """Return whether a mapping filename's experiment id matches a logical leg."""
    leg = _normalize_leg(leg)
    exp = experiment.lower()
    if leg == LEG_RAMP_UP:
        return exp == DEFAULT_EXPERIMENT
    if leg == LEG_RAMP_DOWN_2C:
        if "dn2p0" not in exp and "dn-" not in exp:
            return False
        return any(token in exp for token in ("gwl2p0", "swl2p0", "50y-2p0", "2p0-50y"))
    if leg == LEG_RAMP_DOWN_4C:
        if "dn2p0" not in exp and "dn-" not in exp:
            return False
        return any(token in exp for token in ("gwl4p0", "swl4p0", "50y-4p0", "4p0-50y"))
    raise ValueError(f"unknown leg {leg!r}")


def _leg_for_experiment(experiment: str) -> str | None:
    """Return the logical leg for an experiment id, or ``None`` if unsupported."""
    for leg in _KNOWN_LEGS:
        if _experiment_matches_leg(experiment, leg):
            return leg
    return None


def _experiment_bundle_priority(experiment: str) -> tuple[int, str]:
    """Sort key for choosing one mapping file per model/leg (lower is preferred)."""
    exp = experiment.lower()
    if exp == DEFAULT_EXPERIMENT:
        tier = 0
    elif exp.startswith("esm-up2p0-"):
        tier = 0
    else:
        tier = 1
    return tier, exp


def _resolve_mapping_candidates(candidates: list[Path]) -> Path:
    """Pick a single mapping file when several match the same model and leg."""
    by_name: dict[str, Path] = {}
    for candidate in candidates:
        by_name.setdefault(candidate.name, candidate)
    unique = list(by_name.values())
    if len(unique) == 1:
        return unique[0]

    ranked = sorted(
        unique,
        key=lambda path: _experiment_bundle_priority(
            _parse_mapping_filename(path)[1]  # type: ignore[index]
        ),
    )
    best = _experiment_bundle_priority(_parse_mapping_filename(ranked[0])[1])  # type: ignore[index]
    tied = [
        path
        for path in ranked
        if _experiment_bundle_priority(_parse_mapping_filename(path)[1]) == best  # type: ignore[index]
    ]
    if len(tied) == 1:
        return tied[0]

    names = ", ".join(p.name for p in tied)
    raise ValueError(f"ambiguous mapping files: {names}")


def _mapping_search_roots(
    mapping_dir: Path | str | None,
    leg: str,
) -> list[Path]:
    """Directories to scan for ``gwlmap_*.nc`` files."""
    leg = _normalize_leg(leg)
    roots: list[Path] = []
    if mapping_dir is not None:
        roots.append(Path(mapping_dir))
    elif leg == LEG_RAMP_UP:
        roots.append(bundled_mappings_dir())
    else:
        roots.append(bundled_mappings_dir())
    seen: set[Path] = set()
    ordered: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(root)
    return ordered


def resolve_mapping_path(
    model: str,
    *,
    leg: str = LEG_RAMP_UP,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str | None = None,
    mapping_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:
    """Locate a ``gwlmap_*.nc`` file for ``model`` without loading it."""
    if path is not None:
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(f"mapping file not found: {src}")
        return src

    leg = _normalize_leg(leg)

    if experiment is not None:
        for root in _mapping_search_roots(mapping_dir, leg):
            candidate = root / f"gwlmap_{model}_{experiment}_{version}.nc"
            if candidate.is_file():
                return candidate
        if leg == LEG_RAMP_UP and experiment == DEFAULT_EXPERIMENT and mapping_dir is None:
            return bundled_mapping_path(model, version=version, experiment=experiment)
        raise FileNotFoundError(
            f"no mapping for {model!r} (experiment={experiment!r}, version={version})"
        )

    if leg == LEG_RAMP_UP and mapping_dir is None:
        try:
            return bundled_mapping_path(model, version=version)
        except FileNotFoundError:
            pass

    candidates: list[Path] = []
    for root in _mapping_search_roots(mapping_dir, leg):
        if not root.is_dir():
            continue
        for candidate in sorted(root.glob(f"gwlmap_{model}_*_{version}.nc")):
            parsed = _parse_mapping_filename(candidate)
            if parsed is None:
                continue
            if _experiment_matches_leg(parsed[1], leg):
                candidates.append(candidate)

    if candidates:
        return _resolve_mapping_candidates(candidates)

    searched = ", ".join(str(r) for r in _mapping_search_roots(mapping_dir, leg))
    raise FileNotFoundError(
        f"no mapping for {model!r} (leg={leg!r}, version={version}); searched: {searched}"
    )


def package_repo_root() -> Path:
    """Root of the installed ``tipmip-gwl`` source tree."""
    return Path(__file__).resolve().parents[2]


def default_mappings_dir() -> Path:
    """Bundled ``mapping/`` directory in this repo, or ``TIPMIP_GWL_MAPPINGS`` override."""
    if raw := os.environ.get(MAPPINGS_ENV_VAR):
        return Path(raw).expanduser()
    return package_repo_root() / MAPPINGS_DIR_NAME


def bundled_mappings_dir() -> Path:
    """Directory of published ``gwlmap_*.nc`` files shipped with this repository."""
    global _WARNED_MISSING_MAPPINGS
    root = default_mappings_dir()
    if not root.is_dir() and not _WARNED_MISSING_MAPPINGS:
        warnings.warn(
            f"Mapping data directory not found: {root}. "
            f"Clone tipmip-gwl with mapping/ included or set {MAPPINGS_ENV_VAR}. "
            "See README.md.",
            stacklevel=2,
        )
        _WARNED_MISSING_MAPPINGS = True
    return root


def _parse_mapping_filename(path: Path) -> tuple[str, str, str] | None:
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None
    return m.group("model"), m.group("experiment"), m.group("version")


def list_models(
    *,
    leg: str = LEG_RAMP_UP,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str | None = None,
    mapping_dir: Path | str | None = None,
) -> list[str]:
    """Return sorted included model ids with a bundled mapping file for ``leg``.

    Only models in :data:`~tipmip_gwl.ensemble.INCLUDED_MODELS` are returned;
    extra files in ``mapping_dir`` for other models are ignored.
    """
    leg = _normalize_leg(leg)
    found: set[str] = set()
    for root in _mapping_search_roots(mapping_dir, leg):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("gwlmap_*.nc")):
            parsed = _parse_mapping_filename(path)
            if parsed is None:
                continue
            model, exp, ver = parsed
            if model not in INCLUDED_MODELS:
                continue
            if ver != version:
                continue
            if experiment is not None:
                if exp != experiment:
                    continue
            elif not _experiment_matches_leg(exp, leg):
                continue
            found.add(model)
    return [model for model in INCLUDED_MODELS if model in found]


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
            f"no mapping for {model!r} ({experiment}, {version}) in "
            f"{bundled_mappings_dir()}; "
            f"available models: {available or '(none — rebuild or obtain mapping/ products)'}"
        )
    return path


def load_mapping(
    model: str,
    *,
    leg: str = LEG_RAMP_UP,
    version: str = DEFAULT_MAPPING_VERSION,
    experiment: str | None = None,
    mapping_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> xr.Dataset:
    """Load a mapping product into memory.

    By default opens the bundled **ramp-up** mapping. Ramp-down legs
    (``"ramp-down-2c"``, ``"ramp-down-4c"``) are also bundled — pass ``leg=``
    to select them. By default reads from ``mapping/`` in this repository (or
    ``TIPMIP_GWL_MAPPINGS``). Long CMIP ``experiment_id`` strings and explicit
    ``path=`` are escape hatches for advanced use.

    Parameters
    ----------
    model : str
        Model id (e.g. ``"GFDL-ESM2M"``), matching the ``gwlmap_`` filename.
    leg : str
        Logical leg: ``"ramp-up"`` (default), ``"ramp-down-2c"``, or
        ``"ramp-down-4c"``. Resolves NorESM ``swl``/standard ``gwl`` names
        automatically when scanning ``mapping_dir``.
    experiment : str, optional
        Exact CMIP experiment id (overrides ``leg`` filename matching).
    mapping_dir : path-like, optional
        Directory of ``gwlmap_*.nc`` files. Default: ``mapping/`` in this repo
        (see :func:`default_mappings_dir`).
    path : path-like, optional
        Open this file directly (bypasses ``leg`` / ``mapping_dir`` search).
    """
    src = resolve_mapping_path(
        model,
        leg=leg,
        version=version,
        experiment=experiment,
        mapping_dir=mapping_dir,
        path=path,
    )
    with xr.open_dataset(src) as ds:
        return ds.load()


def _year_of_gwl_target(
    mapping_ds: xr.Dataset,
    *,
    gwl_step: float | None = None,
    gwl_min: float | None = None,
    gwl_max: float | None = None,
) -> xr.DataArray:
    """Fractional model year at each GWL on the requested grid (for ``resample_to_gwl``).

    By default uses the ``gwl`` coordinate stored in ``mapping_ds`` (ramp-up
    0–4 °C or ramp-down −2–5 °C, etc.). Pass ``gwl_step`` / ``gwl_min`` /
    ``gwl_max`` to narrow the grid, or change its spacing, within that stored
    range. These cannot *extend* coverage beyond what the file has: the
    inverse map ``year_of_gwl`` is only tabulated on the stored ``gwl`` range,
    so a wider request is clamped back to it (with a warning) rather than
    silently returning NaN outside it. To cover a wider GWL range, rebuild the
    mapping product with a wider ``T_grid`` (see :mod:`tipmip_gwl.build`).
    """
    src_gwl = np.asarray(mapping_ds["gwl"].values, dtype=float)
    src_years = np.asarray(mapping_ds["year_of_gwl"].values, dtype=float)
    finite = np.isfinite(src_years) & np.isfinite(src_gwl)
    if finite.sum() < 2:
        raise ValueError("mapping_ds['year_of_gwl'] has too few finite values")

    src_lo, src_hi = float(np.nanmin(src_gwl)), float(np.nanmax(src_gwl))

    if gwl_step is None and gwl_min is None and gwl_max is None:
        grid = src_gwl
    else:
        step = mapping.GWL_GRID_STEP if gwl_step is None else gwl_step
        lo = src_lo if gwl_min is None else gwl_min
        hi = src_hi if gwl_max is None else gwl_max

        if lo < src_lo:
            warnings.warn(
                f"requested gwl_min={lo:g} is below this file's stored range "
                f"({src_lo:g}\u2013{src_hi:g} \u00b0C); clamping to {src_lo:g}. "
                "resample_to_gwl cannot extend coverage beyond what the "
                "mapping product stores -- rebuild with a wider T_grid to "
                "cover a lower GWL.",
                stacklevel=3,
            )
            lo = src_lo
        if hi > src_hi:
            warnings.warn(
                f"requested gwl_max={hi:g} is above this file's stored range "
                f"({src_lo:g}\u2013{src_hi:g} \u00b0C); clamping to {src_hi:g}. "
                "resample_to_gwl cannot extend coverage beyond what the "
                "mapping product stores -- rebuild with a wider T_grid to "
                "cover a higher GWL.",
                stacklevel=3,
            )
            hi = src_hi

        grid = gwl_grid(step, hi, gwl_min=lo)

    years = np.interp(
        grid, src_gwl[finite], src_years[finite], left=np.nan, right=np.nan
    )
    return xr.DataArray(years, dims=["gwl"], coords={"gwl": ("gwl", grid)})


def resample_to_gwl(
    mapping_ds,
    data,
    year_dim="year",
    *,
    gwl_step: float | None = None,
    gwl_min: float | None = None,
    gwl_max: float | None = None,
):
    """Resample a diagnostic from calendar time onto the common GWL grid.

    This is the operational use of a mapping file: it applies ``year_of_gwl``
    (the inverse transform t(GWL)) to your own variable, returning it indexed by
    ``gwl`` so models can be stacked on the shared axis.

    Parameters
    ----------
    mapping_ds : x.Dataset
        A mapping product (from :func:`tipmip_gwl.build.build_mapping_dataset` or a published
        ``gwlmap_*.nc``). By default the output ``gwl`` coordinate matches the
        grid stored in the file (0–4 °C for ramp-up, −2–5 °C for ramp-down).
        Optional ``gwl_step`` / ``gwl_min`` / ``gwl_max`` refine or
        subset that grid.
    data : x.DataArray or x.Dataset
        The diagnostic on an **annual** axis whose coordinate values are calendar
        years (named ``year_dim``). Alignment is by coordinate *value*, so the
        diagnostic need not start on the same year or have the same length as the
        ramp-up; non-overlapping years simply map to NaN.
    year_dim : str
        Name of the annual coordinate on ``data`` (default ``"year"``).
    gwl_step, gwl_min, gwl_max : float, optional
        Custom GWL grid. If all are omitted, uses ``mapping_ds['gwl']`` as-is.
        Can narrow the range or change the spacing, but cannot extend
        coverage beyond the file's stored ``gwl`` range: a wider request is
        clamped back to it (with a warning), since ``year_of_gwl`` has no
        data outside that range to interpolate from.

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
    target = _year_of_gwl_target(
        mapping_ds, gwl_step=gwl_step, gwl_min=gwl_min, gwl_max=gwl_max
    )
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

