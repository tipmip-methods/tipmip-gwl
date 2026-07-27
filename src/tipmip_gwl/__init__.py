"""
tipmip_gwl
==========
Re-index TIPMIP model output onto a global warming level (GWL) axis.

User API::

    from tipmip_gwl import load_mapping, list_models, resample_to_gwl, relabel_to_gwl

Maintainer tooling lives outside the package: ``scripts/build_gmstmon.py``,
``scripts/run_diagnostics.py``, ``tipmip_gwl.build``, and ``paper/``.
"""

from .product import (
    DEFAULT_MAPPING_VERSION,
    LEG_RAMP_DOWN_2C,
    LEG_RAMP_DOWN_4C,
    LEG_RAMP_UP,
    load_mapping,
    list_models,
    relabel_to_gwl,
    resample_to_gwl,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_MAPPING_VERSION",
    "LEG_RAMP_UP",
    "LEG_RAMP_DOWN_2C",
    "LEG_RAMP_DOWN_4C",
    "load_mapping",
    "list_models",
    "resample_to_gwl",
    "relabel_to_gwl",
    "__version__",
]
