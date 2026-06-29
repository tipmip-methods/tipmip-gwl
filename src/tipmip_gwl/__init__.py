"""
tipmip_gwl
==========
Re-index TIPMIP ramp-up model output from a time axis onto a common global
warming level (GWL / GMSAT-anomaly) axis, so models can be compared at the same
warming level rather than the same calendar year.

Two layers:

* :mod:`tipmip_gwl.mapping` -- the pure numpy/scipy algorithm (baseline ->
  anomaly -> monotone temperature axis -> invert -> resample). No file-format
  knowledge; works on (years, values) arrays.
* :mod:`tipmip_gwl.tipmip` -- TIPMIP/NetCDF glue: read global-mean ``tas``,
  decode branch years from CMIP metadata, enforce provenance, run diagnostics
  and figures.
"""

from . import mapping, tipmip
from .mapping import (
    MappingConfig,
    ModelMapping,
    axis_variable,
    invert_to_grid,
    map_model,
    monotonicity_report,
    picontrol_drift,
    picontrol_reference,
    resample_variable,
    sensitivity_matrix,
    stack_models,
    to_anomaly,
)
from .tipmip import (
    Baseline,
    BranchInfo,
    branch_year_from_attrs,
    compute_baseline,
    load_gmsat_nc,
    plot_diagnostics,
    provenance_check,
    run_diagnostics,
)

__version__ = "0.1.0"

__all__ = [
    "mapping",
    "tipmip",
    # mapping
    "MappingConfig",
    "ModelMapping",
    "map_model",
    "axis_variable",
    "invert_to_grid",
    "resample_variable",
    "monotonicity_report",
    "picontrol_drift",
    "picontrol_reference",
    "sensitivity_matrix",
    "stack_models",
    "to_anomaly",
    # tipmip
    "Baseline",
    "BranchInfo",
    "branch_year_from_attrs",
    "compute_baseline",
    "load_gmsat_nc",
    "plot_diagnostics",
    "provenance_check",
    "run_diagnostics",
]
