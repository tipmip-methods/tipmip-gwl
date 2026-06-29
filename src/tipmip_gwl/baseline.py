"""
baseline.py
===========
Establish the anomaly zero point for each model from its TIPMIP file: decide
whether the run is admissible, where it branched, and what its piControl
reference is. The provenance and branch-year steps read CMIP-standard global
attributes; the reference is the protocol piControl mean those steps feed.

It provides:

* :func:`provenance_check` -- reject files that are not genuine TIPMIP ramp-up
  submissions before they are mapped.
* :func:`branch_year_from_attrs` -- decode ``branch_time_in_parent`` against the
  parent calendar with ``cftime``, returning year A plus parent run identifiers.
* :func:`compute_baseline` -- protocol piControl reference with an explicit
  ``baseline_method`` flag: it falls back to a *trailing* window when the branch
  sits at/near the start of piControl (e.g. EC-Earth branches at day 0), so that
  per-model inconsistency is surfaced rather than silent.

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
}


# ---------------------------------------------------------------------------
# Provenance gate
# ---------------------------------------------------------------------------
def provenance_check(attrs: dict, expect_experiment: str = "esm-up2p0"):
    """Validate that a ramp-up file is a genuine TIPMIP submission.

    Returns ``(ok, reason)``. A file failing any check is rejected before
    mapping rather than silently processed (e.g. a file staged under a model
    name that is actually a TerraFIRMA run, not TIPMIP).

    ``activity_id`` is matched case-insensitively because submissions use both
    'TIPMIP' and 'TipMIP'. ``branch_method`` is only rejected when it explicitly
    states 'no parent'; a missing value is tolerated so that an otherwise-valid
    file is not rejected on an absent attribute.
    """
    activity = str(attrs.get("activity_id", "")).strip()
    experiment = str(attrs.get("experiment_id", "")).strip()
    branch = str(attrs.get("branch_method", "")).strip().lower()

    if "tipmip" not in activity.lower():
        return False, f"activity_id={activity!r} is not TIPMIP"
    if expect_experiment and experiment != expect_experiment:
        return False, f"experiment_id={experiment!r} != {expect_experiment!r}"
    if branch == "no parent":
        return False, "branch_method='no parent' (no piControl linkage)"
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
        info.note = "branch at parent start (day 0): centred window not possible"
    return info


# ---------------------------------------------------------------------------
# Protocol baseline with explicit method flag
# ---------------------------------------------------------------------------
@dataclass
class Baseline:
    reference: float
    method: str  # e.g. "centred_31yr", "trailing_31yr_day0", "leading_31yr"
    window: int
    n_years: int
    span: tuple
    drift_window_degC_per_century: float
    drift_full_degC_per_century: float
    detrended: bool


def compute_baseline(pi_years, pi_gmsat, branch_year, window=31, detrend=False) -> Baseline:
    """Protocol piControl reference with a fallback window + method flag.

    Centred 31-yr mean on year A when piControl has >= window//2 years either
    side. If the branch is at/near the start (e.g. EC-Earth, day 0) it falls back
    to a *trailing* (first-``window``) mean; near the end, a *leading* (last-
    ``window``) mean. The chosen method is returned so a downstream reader knows
    a model's zero point was computed differently from the centred ones.
    """
    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)
    half = window // 2

    lo, hi = branch_year - half, branch_year + half
    if lo < yrs.min():
        start = yrs.min()
        sel = (yrs >= start) & (yrs < start + window)
        method = f"trailing_{window}yr_day0" if branch_year <= start else f"trailing_{window}yr"
    elif hi > yrs.max():
        sel = yrs > yrs.max() - window
        method = f"leading_{window}yr"
    else:
        sel = (yrs >= lo) & (yrs <= hi)
        method = f"centred_{window}yr"

    g = vals.copy()
    if detrend:
        coef = np.polyfit(yrs, vals, 1)
        g = vals - np.polyval(coef, yrs) + np.polyval(coef, branch_year)

    sel &= np.isfinite(g)
    ref = float(np.mean(g[sel]))

    drift_win = mapping.picontrol_drift(yrs, vals, centre_year=branch_year, window=window)
    drift_full = mapping.picontrol_drift(yrs, vals)

    return Baseline(
        reference=ref,
        method=method,
        window=window,
        n_years=int(sel.sum()),
        span=(float(yrs[sel].min()), float(yrs[sel].max())) if sel.any() else (np.nan, np.nan),
        drift_window_degC_per_century=drift_win["drift_degC_per_century"],
        drift_full_degC_per_century=drift_full["drift_degC_per_century"],
        detrended=detrend,
    )
