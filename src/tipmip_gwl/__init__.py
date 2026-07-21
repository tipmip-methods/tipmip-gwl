"""
tipmip_gwl
==========
Re-index TIPMIP ramp-up model output from a time axis onto a common global
warming level (GWL / GMSAT-anomaly) axis, so models can be compared at the same
warming level rather than the same calendar year.

Modules:

* :mod:`tipmip_gwl.mapping`     -- pure numpy/scipy algorithm (paper Steps
  1–3: anomaly computation -> smoothing and monotonicity -> inversion and
  resampling). No file-format knowledge; works on (years, values) arrays.
* :mod:`tipmip_gwl.io`          -- read global-mean ``tas`` NetCDF and discover
  files on disk.
* :mod:`tipmip_gwl.baseline`    -- establish the anomaly zero point: provenance
  gate, branch-year decode, protocol piControl reference.
* :mod:`tipmip_gwl.diagnostics` -- the driver, sanity table, and CLI.
* :mod:`tipmip_gwl.product`     -- build and load the per-model time<->GWL NetCDF
  product (the transform + diagnostics + provenance), plus the two GWL transforms
  for *continuous* data: ``resample_to_gwl`` (resample onto the shared 0-4 degC
  grid), ``relabel_to_gwl`` (relabel each model's native axis with its own GWL,
  unbinned), and ``load_mapping`` (open bundled published ``gwlmap_*.nc`` files).
* :mod:`tipmip_gwl.rampdown`    -- the same per-model time<->GWL NetCDF product
  for the *ramp-down* leg (monotone non-increasing axis, its own GWL grid).
  A separate product, not a variant of ``product.py``: this leg's parent is
  the zero-emission hold run rather than piControl, and its axis must never
  be equated with the ramp-up leg's at the same GWL (different Earth-system
  state; see the ``mapping.py`` scope notes).
* :mod:`tipmip_gwl.zehold`      -- the zero-emission-hold ("ZE") leg's GWL
  characterisation (``esm-up2p0-gwl2p0``/``gwl4p0`` and variants). A third,
  structurally different product: no monotonicity is enforced (the hold can
  wander -- that wander is the signal), so it ships no ``year_of_gwl`` and no
  common ``gwl`` grid, only the forward ``gwl_axis(year)`` plus per-model
  drift diagnostics (``net_drift``, realised vs. nominal target GWL).
* :mod:`tipmip_gwl.preprocess`   -- build ``gmstmon`` from raw tas chunks
  (:func:`tipmip_gwl.preprocess.build_gmstmon`, CLI ``tipmip-gwl-preprocess``).
* :mod:`tipmip_gwl.plotting`    -- diagnostic figures (needs the ``plot`` extra).
"""

from . import baseline, diagnostics, io, mapping, plotting, product, rampdown, zehold
from .baseline import (
    Baseline,
    BranchInfo,
    branch_year_from_attrs,
    compute_baseline,
    discover_mappable_models,
    branch_window_reference,
    provenance_check,
    provenance_warnings,
    resolve_branch_year,
)
from .diagnostics import ModelDiag, print_table, run_diagnostics
from .io import discover, load_gmsat_nc, read_attrs
from .mapping import (
    MappingConfig,
    ModelMapping,
    axis_variable,
    gwl_grid,
    GWL_GRID_STEP,
    invert_to_grid,
    map_model,
    monotonicity_report,
    picontrol_drift,
    picontrol_reference,
    resample_variable,
    running_mean,
    sensitivity_matrix,
    stack_models,
    to_anomaly,
)
from .plotting import plot_diagnostics
from .product import (
    DEFAULT_MAPPING_VERSION,
    NotMappable,
    build_mapping_dataset,
    bundled_mapping_path,
    bundled_mappings_dir,
    list_models,
    load_mapping,
    relabel_to_gwl,
    resample_to_gwl,
    write_mapping,
    write_products,
)
from .preprocess import build_gmstmon, default_tas_chunks_manifest, load_tas_chunks
from .rampdown import (
    build_rampdown_mapping_dataset,
    write_rampdown_mapping,
    write_rampdown_products,
)
from .zehold import build_ze_mapping_dataset, write_ze_mapping, write_ze_products

__version__ = "0.1.0"

__all__ = [
    # submodules
    "mapping",
    "io",
    "baseline",
    "diagnostics",
    "product",
    "rampdown",
    "zehold",
    "plotting",
    # mapping
    "MappingConfig",
    "ModelMapping",
    "gwl_grid",
    "GWL_GRID_STEP",
    "map_model",
    "axis_variable",
    "invert_to_grid",
    "resample_variable",
    "running_mean",
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
    "discover_mappable_models",
    "branch_window_reference",
    "provenance_check",
    "provenance_warnings",
    "resolve_branch_year",
    # diagnostics / plotting
    "ModelDiag",
    "run_diagnostics",
    "print_table",
    "plot_diagnostics",
    # product
    "DEFAULT_MAPPING_VERSION",
    "NotMappable",
    "build_mapping_dataset",
    "bundled_mapping_path",
    "bundled_mappings_dir",
    "list_models",
    "load_mapping",
    "resample_to_gwl",
    "relabel_to_gwl",
    "write_mapping",
    "write_products",
    # rampdown
    "build_rampdown_mapping_dataset",
    "write_rampdown_mapping",
    "write_rampdown_products",
    # zehold
    "build_ze_mapping_dataset",
    "write_ze_mapping",
    "write_ze_products",
    # preprocess
    "build_gmstmon",
    "default_tas_chunks_manifest",
    "load_tas_chunks",
]
