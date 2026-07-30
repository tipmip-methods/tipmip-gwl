"""Included Tier-1 ensemble — single source of truth for builds and figures."""

from __future__ import annotations

from pathlib import Path

INCLUDED_MODELS: tuple[str, ...] = (
    "ACCESS-ESM1-5",
    "EC-Earth3-ESM-1",
    "GFDL-ESM2M",
    "GISS-E2-1-G-CC2",
    "IPSL-CM6-ESMCO2",
    "MIROC-ES2L",
    "NorESM2-LM",
    "UKESM1-2-LL",
)

# Gmstmon experiment ids needed for a full mapping + paper rebuild (each dir
# holds one *_gmstmon.nc per model in INCLUDED_MODELS).
REQUIRED_GMSTMON_EXPERIMENTS: tuple[str, ...] = (
    "esm-up2p0",
    "esm-piControl",
    "esm-up2p0-gwl2p0-50y-dn2p0",
    "esm-up2p0-gwl4p0-50y-dn2p0",
)

DEFAULT_STAGED_ROOT = Path.home() / "data/tipmip"


class MissingEnsembleDataError(Exception):
    """Raised when staged data or mapping products omit an included model."""


def included_models() -> tuple[str, ...]:
    """Return the canonical included model ids (alphabetical)."""
    return INCLUDED_MODELS


def required_gmstmon_experiments() -> tuple[str, ...]:
    """Return experiment ids that must be staged under ``<root>/tas/<exp>/gmstmon/``."""
    return REQUIRED_GMSTMON_EXPERIMENTS


def resolve_model_list(models: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalise an optional override; default is :data:`INCLUDED_MODELS`."""
    if models is None:
        return INCLUDED_MODELS
    return tuple(models)


def require_discovered(
    models: tuple[str, ...],
    discovered: dict[str, object],
    *,
    label: str,
) -> None:
    """Raise if any ``models`` lack an entry in ``discovered``."""
    missing = [m for m in models if m not in discovered]
    if missing:
        raise MissingEnsembleDataError(
            f"Missing {label} gmstmon for included model(s): {', '.join(missing)}"
        )


def require_mapping_index(
    models: tuple[str, ...],
    index: dict[str, Path],
    *,
    leg: str,
) -> None:
    """Raise if any ``models`` lack a mapping file in ``index``."""
    missing = [m for m in models if m not in index]
    if missing:
        raise MissingEnsembleDataError(
            f"Missing {leg} mapping for included model(s): {', '.join(missing)}"
        )
