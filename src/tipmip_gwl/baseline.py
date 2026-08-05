"""
baseline.py
===========
Establish the anomaly zero point for each model from its TIPMIP file: decide
whether the run is admissible, where it branched, and what its piControl
reference is the 31-yr branch-window mean at the decoded branch year when
possible, otherwise the full piControl mean.

It provides:

* :func:`provenance_warnings` -- flag imperfect CMIP linkage (wrong experiment id,
  missing parent metadata) without blocking mapping when piControl is available.
* :func:`provenance_check` -- kept for compatibility; always passes (see warnings).
* :func:`branch_year_from_attrs` -- decode ``branch_time_in_parent`` against the
  parent calendar with ``cftime``, returning year A plus parent run identifiers.
* :func:`branch_window_reference` -- centred ``window``-yr piControl mean at the
  branch year (trailing first ``window`` years when the branch is at piControl start).
* :func:`compute_baseline` -- published piControl reference via
  :func:`branch_window_reference` when the branch year lies in the staged control,
  otherwise the full piControl mean.

Dependencies: numpy, cftime, and the sibling :mod:`tipmip_gwl.mapping`.
"""

from __future__ import annotations

from dataclasses import dataclass

import cftime
import numpy as np

from . import mapping

# Branch years independently decoded from headers (optional cross-check).
# A mismatch here flags a metadata/units problem, not science.
KNOWN_BRANCH_YEARS = {
    "GFDL-ESM2M": 1961,
    "GISS-E2-1-G-CC2": 2156,
    "IPSL-CM6-ESMCO2": 1850,
    "EC-Earth3-ESM-1": 1850,
    "NorESM2-LM": 1851,  # patched; CMIP attrs wrongly decode to 1600
    "UKESM1-2-LL": 2277,  # manually patched; branched from piControl year 2277
}


# ---------------------------------------------------------------------------
# Provenance / eligibility
# ---------------------------------------------------------------------------
def provenance_warnings(attrs: dict, expect_experiment: str = "esm-up2p0") -> list[str]:
    """Non-fatal metadata issues on a ramp-up file.

    Imperfect metadata is non-fatal — mapping proceeds when a matching piControl
    file is available on disk.
    """
    warns = []
    experiment = str(attrs.get("experiment_id", "")).strip()
    branch = str(attrs.get("branch_method", "")).strip().lower()

    if expect_experiment and experiment != expect_experiment:
        warns.append(f"experiment_id={experiment!r} != {expect_experiment!r}")
    if branch == "no parent":
        warns.append("branch_method='no parent' (no parent linkage in metadata)")
    if (
        attrs.get("branch_time_in_parent") is None
        or attrs.get("parent_time_units") is None
    ):
        warns.append("missing branch_time_in_parent/parent_time_units")
    return warns


def provenance_check(attrs: dict, expect_experiment: str = "esm-up2p0"):
    """Always ``(True, '')``; see :func:`provenance_warnings` for metadata flags."""
    return True, ""


# ---------------------------------------------------------------------------
# Branch-point decoding
# ---------------------------------------------------------------------------
@dataclass
class BranchInfo:
    year: int | None
    parent_source_id: str | None = None
    parent_variant_label: str | None = None
    parent_experiment_id: str | None = None
    parent_activity_id: str | None = None
    parent_mip_era: str | None = None
    calendar: str | None = None
    at_parent_start: bool = False  # branch_time_in_parent == 0
    raw_branch_time: float | None = None
    note: str = ""


def branch_year_from_attrs(attrs: dict, calendar: str | None = None) -> BranchInfo:
    """Decode year A from CMIP ``branch_time_in_parent`` against the parent calendar.

    ``calendar`` defaults to the child file's time calendar (same model => same
    calendar as the parent). Decode with cftime, never days/365.25, because for
    a noleap calendar the offset is an exact multiple of 365 and 365.25 arithmetic
    walks off by up to a year.
    """
    bt = attrs.get("branch_time_in_parent")
    units = attrs.get("parent_time_units")
    cal = calendar or attrs.get("_time_calendar") or attrs.get("calendar") or "standard"

    info = BranchInfo(
        year=None,
        parent_source_id=attrs.get("parent_source_id"),
        parent_variant_label=attrs.get("parent_variant_label"),
        parent_experiment_id=attrs.get("parent_experiment_id"),
        parent_activity_id=attrs.get("parent_activity_id"),
        parent_mip_era=attrs.get("parent_mip_era"),
        calendar=cal,
        raw_branch_time=None if bt is None else float(bt),
    )

    if bt is None or units is None:
        info.note = "missing branch_time_in_parent/parent_time_units"
        return info

    try:
        date = cftime.num2date(float(bt), units=units, calendar=cal)
    except Exception as exc:  # noqa: BLE001
        info.note = f"cftime decode failed: {exc}"
        return info

    info.year = int(date.year)
    info.at_parent_start = float(bt) == 0.0
    if info.at_parent_start:
        info.note = "branch at parent start (day 0)"
    return info


def _has_declared_parent(bi: BranchInfo) -> bool:
    """Whether the file declares a parent run at all (independent of the year)."""
    return bool(bi.parent_source_id or bi.parent_experiment_id)


def resolve_branch_year(bi: BranchInfo, model: str, ru_years=None, pi_years=None):
    """Return ``(branch_year, warnings)`` from decoded CMIP branch metadata.

    ``ru_years`` is accepted for call-site compatibility but is not used as a
    fallback.

    This never raises: a missing or undecodable branch year is reported as a
    *warning*, distinguishing (for traceability) whether no parent was declared
    at all (``branch_method == 'no parent'`` and no ``parent_source_id``/
    ``parent_experiment_id``) versus a parent being declared but the year
    specifically not decodable (e.g. a malformed ``branch_time_in_parent``/
    ``parent_time_units``). Either way the model remains mappable and
    :func:`compute_baseline` falls back to the full piControl mean. The sole
    hard requirement for mapping a model is having a piControl tas file to pair
    it with at all (enforced by the caller, not here).

    A branch year outside the staged piControl span is also a warning, not a
    fatal error: :func:`compute_baseline` falls back to the full piControl mean
    in that case too (NorESM2-LM).
    """
    del ru_years  # kept for a stable signature; no ramp-up-start fallback
    warns = []
    known = KNOWN_BRANCH_YEARS.get(model)

    if bi.year is None:
        if not _has_declared_parent(bi):
            warns.append(
                "no parent run declared (branch_method='no parent' or missing "
                "parent_source_id/parent_experiment_id); baseline computed from "
                "full piControl only, paired by filename"
            )
        else:
            warns.append(
                f"branch year could not be decoded "
                f"({bi.note or 'missing branch_time_in_parent/parent_time_units'}); "
                f"baseline computed from full piControl only"
            )
        return None, warns

    branch = bi.year

    if known is not None and known != bi.year:
        warns.append(f"branch-year mismatch: decoded {bi.year} vs known {known}")

    if pi_years is not None:
        pi_lo, pi_hi = float(np.min(pi_years)), float(np.max(pi_years))
        if not (pi_lo <= branch <= pi_hi):
            warns.append(
                f"branch year {branch} outside staged piControl span "
                f"[{int(pi_lo)}-{int(pi_hi)}]; baseline falls back to full "
                f"piControl mean, which does not cover the branch year"
            )
    return branch, warns


def branch_window_reference(
    pi_years,
    pi_gmsat,
    branch_year,
    window: int = 31,
) -> float:
    """Centred ``window``-yr piControl mean at the branch year.

    When the centred window would extend before piControl start (e.g. branch at
    parent day 0), use the first ``window`` years of piControl instead.
    """
    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)
    finite = np.isfinite(yrs) & np.isfinite(vals)
    half = window // 2
    lo, hi = branch_year - half, branch_year + half
    pi_lo, pi_hi = float(yrs.min()), float(yrs.max())

    if lo < pi_lo:
        sel = (yrs >= pi_lo) & (yrs < pi_lo + window) & finite
    elif hi > pi_hi:
        raise ValueError(
            f"centred {window}-yr window [{int(lo)}-{int(hi)}] not contained in "
            f"piControl [{int(pi_lo)}-{int(pi_hi)}]"
        )
    else:
        sel = (yrs >= lo) & (yrs <= hi) & finite

    if sel.sum() == 0:
        raise ValueError(f"no piControl data in {window}-yr branch reference window")
    return float(np.mean(vals[sel]))


def discover_mappable_models(up2p0_dir, picontrol_dir, *, bundled_only=False):
    """Yield ``(model, ramp_up_path, picontrol_path)`` for models with piControl tas."""
    from .io import discover

    if bundled_only:
        from tipmip_gwl.ensemble import INCLUDED_MODELS

        allowed = set(INCLUDED_MODELS)
    else:
        allowed = None

    ru_files = discover(up2p0_dir)
    pi_files = discover(picontrol_dir)
    for model in sorted(ru_files):
        if allowed is not None and model not in allowed:
            continue
        pi_path = pi_files.get(model)
        if pi_path is None:
            continue
        yield model, ru_files[model], pi_path


# ---------------------------------------------------------------------------
# Protocol baseline
# ---------------------------------------------------------------------------
@dataclass
class Baseline:
    reference: float
    method: str
    n_years: int
    span: tuple
    drift_degC_per_century: float
    detrended: bool


def compute_baseline(
    pi_years,
    pi_gmsat,
    branch_year=None,
    *,
    detrend=False,
    window: int = 31,
) -> Baseline:
    """Published piControl reference GMSAT for the anomaly baseline.

    Uses a ``window``-yr mean centred on ``branch_year`` when the branch year
    is decodable and lies inside the staged piControl span; trailing first
    ``window`` years when the centred window would start before piControl
    (ACCESS-ESM1-5, EC-Earth3-ESM-1). Falls back to the full piControl mean
    when ``branch_year`` is missing or outside the control span (NorESM2-LM).

    Drift and span always refer to the full piControl record. When
    ``detrend=True``, the full-run mean with linear detrend is used (requires
    ``branch_year``).
    """
    if detrend and branch_year is None:
        raise ValueError("branch_year is required when detrend=True")
    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)

    finite = np.isfinite(yrs) & np.isfinite(vals)
    drift = mapping.picontrol_drift(yrs, vals)
    pi_lo = float(yrs[finite].min()) if finite.any() else float("nan")
    pi_hi = float(yrs[finite].max()) if finite.any() else float("nan")

    if detrend:
        ref = mapping.picontrol_reference(yrs, vals, branch_year, detrend=True)
        method = "full_piControl_mean_detrended"
    elif branch_year is None:
        ref = mapping.picontrol_reference(yrs, vals, branch_year, detrend=False)
        method = "full_piControl_mean_no_branch_year"
    elif not (pi_lo <= float(branch_year) <= pi_hi):
        ref = mapping.picontrol_reference(yrs, vals, branch_year, detrend=False)
        method = "full_piControl_mean"
    else:
        half = window // 2
        trailing = (float(branch_year) - half) < pi_lo
        ref = branch_window_reference(yrs, vals, branch_year, window=window)
        method = (
            "branch_window_31yr_trailing"
            if trailing
            else f"branch_window_{window}yr"
        )

    return Baseline(
        reference=ref,
        method=method,
        n_years=int(finite.sum()),
        span=(pi_lo, pi_hi) if finite.any() else (np.nan, np.nan),
        drift_degC_per_century=drift["drift_degC_per_century"],
        detrended=detrend,
    )
