"""
tipmip_gwl
==========
Re-index TIPMIP ramp-up model output from a time axis onto a common global
warming level (GWL / GMSAT-anomaly) axis, so models can be compared at the same
warming level rather than the same calendar year.

Modules:

* :mod:`tipmip_gwl.mapping`     -- pure numpy/scipy algorithm (baseline ->
  anomaly -> monotone temperature axis -> invert -> resample). No file-format
  knowledge; works on (years, values) arrays.
* :mod:`tipmip_gwl.io`          -- read global-mean ``tas`` NetCDF and discover
  files on disk.
* :mod:`tipmip_gwl.baseline`    -- establish the anomaly zero point: provenance
  gate, branch-year decode, protocol piControl reference.
* :mod:`tipmip_gwl.diagnostics` -- the driver, sanity table, and CLI.
* :mod:`tipmip_gwl.product`     -- build the per-model time<->GWL NetCDF product
  (the transform + diagnostics + provenance) that ships alongside the data.
* :mod:`tipmip_gwl.plotting`    -- diagnostic figures (needs the ``plot`` extra).
"""

from . import baseline, diagnostics, io, mapping, plotting, product
from .baseline import (
    Baseline,
    BranchInfo,
    branch_year_from_attrs,
    compute_baseline,
    provenance_check,
)
from .diagnostics import ModelDiag, print_table, run_diagnostics
from .io import discover, load_gmsat_nc, read_attrs
from .product import (
    NotMappable,
    build_mapping_dataset,
    write_mapping,
    write_products,
)
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
from .plotting import plot_diagnostics

__version__ = "0.1.0"

__all__ = [
    # submodules
    "mapping",
    "io",
    "baseline",
    "diagnostics",
    "product",
    "plotting",
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
    # io
    "load_gmsat_nc",
    "read_attrs",
    "discover",
    # cmip
    "Baseline",
    "BranchInfo",
    "branch_year_from_attrs",
    "compute_baseline",
    "provenance_check",
    # diagnostics / plotting
    "ModelDiag",
    "run_diagnostics",
    "print_table",
    "plot_diagnostics",
    # product
    "NotMappable",
    "build_mapping_dataset",
    "write_mapping",
    "write_products",
]
