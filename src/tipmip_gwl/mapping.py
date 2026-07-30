"""
mapping.py
==========
Pure (numpy/scipy) re-indexing of a time series onto a common TEMPERATURE
(GMSAT-anomaly) axis, so models can be stacked and compared at a common global
warming level (GWL) rather than at a common year.

This module is deliberately free of any file-format or CMIP knowledge: it works
on plain (years, values) arrays. The TIPMIP/NetCDF-specific glue lives in
:mod:`tipmip_gwl.io`.

Scope / assumptions
-------------------
* Works on a single monotonic leg at a time: the *ramp-up* (esm-up2p0,
  ``direction="increasing"``, the default) or the *ramp-down*
  (esm-up2p0-*-dn2p0, ``direction="decreasing"``). On a single monotonic path,
  temperature-matching is well posed. Do NOT reuse either leg's axis to equate
  its state with the *other* leg's state at the same GWL: same GWL on
  different paths is a different Earth-system state. That path-dependence is a
  science target, not a nuisance to interpolate away.
* Do not run this across a combined up+hold+down trajectory either: GWL is not
  monotonic over that full span (up, then flat, then down), so no single
  ``direction`` fits it. The zero-emission hold leg needs no monotone axis at
  all (see the paper draft); build each leg's mapping independently.
* Baseline (the zero of the anomaly) is defined in :mod:`tipmip_gwl.baseline`
  (default: 31-yr branch-window mean from piControl when branch metadata
  allows, otherwise full piControl mean). This module only consumes the
  resulting reference value.

Pipeline (paper Steps 1–3)
--------------------------
1. **Anomaly computation** — :func:`picontrol_reference`, :func:`to_anomaly`;
   GMSAT I/O in :mod:`tipmip_gwl.io`; archive preprocessing in ``scripts/build_gmstmon.py``.
2. **Smoothing and monotonicity** — :func:`axis_variable`,
   :func:`monotonicity_report`.
3. **Inversion and resampling** — :func:`invert_to_grid`,
   :func:`resample_variable`; product wrappers in :mod:`tipmip_gwl.product`.

Dependencies: numpy, scipy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator


# ---------------------------------------------------------------------------
# Baseline / anomaly
# ---------------------------------------------------------------------------
def picontrol_reference(pi_years, pi_gmsat, branch_year, *, detrend=False):
    """Full-run mean piControl GMSAT for the anomaly baseline.

    Parameters
    ----------
    branch_year : the piControl calendar year the ramp-up was branched from;
                  used only when ``detrend=True`` to set the detrended offset.
    detrend     : if True, linearly detrend piControl before taking the mean
                  (must be applied consistently across ALL models and reported).
    """
    yrs = np.asarray(pi_years, float)
    g = np.asarray(pi_gmsat, float).copy()
    if detrend:
        coef = np.polyfit(yrs, g, 1)
        g = g - np.polyval(coef, yrs) + np.polyval(coef, branch_year)
    finite = np.isfinite(yrs) & np.isfinite(g)
    if finite.sum() == 0:
        raise ValueError("No finite piControl GMSAT values.")
    return float(np.mean(g[finite]))


def to_anomaly(ru_years, ru_gmsat, pi_reference):
    """Ramp-up GMSAT expressed as an anomaly relative to the piControl ref."""
    return ru_gmsat - pi_reference


def picontrol_drift(pi_years, pi_gmsat):
    """Linear drift of the full piControl GMSAT series, in degC per century.

    Report this next to ``pi_reference_GMSAT`` for every model before trusting
    a baseline; sizeable drift means the full-run mean may still be sensitive
    to control length.

    Returns
    -------
    dict with ``drift_degC_per_century``, ``n_years``, and the ``(lo, hi)`` years
    the fit spanned.
    """
    yrs = np.asarray(pi_years, float)
    vals = np.asarray(pi_gmsat, float)

    yrs_s, vals_s = yrs, vals
    good = np.isfinite(yrs_s) & np.isfinite(vals_s)
    yrs_s, vals_s = yrs_s[good], vals_s[good]
    if yrs_s.size < 2:
        return {
            "drift_degC_per_century": float("nan"),
            "n_years": int(yrs_s.size),
            "span": (float("nan"), float("nan")),
        }

    slope = np.polyfit(yrs_s, vals_s, 1)[0]
    return {
        "drift_degC_per_century": float(slope * 100.0),
        "n_years": int(yrs_s.size),
        "span": (float(yrs_s.min()), float(yrs_s.max())),
    }


# ---------------------------------------------------------------------------
# Monotone axis variable T~(t)
# ---------------------------------------------------------------------------
def running_mean(years, values, window):
    """Centred running mean on a (assumed) 1-year cadence. Edges shrink window.

    Public on its own (not only reachable via :func:`axis_variable`) because
    the zero-emission-hold leg wants smoothing WITHOUT the monotonicity step:
    its trajectory can genuinely wander during the hold, and that wander is
    the signal, not noise to force away. A short hold (e.g. 50 years) is also
    a poor match for a 31-year window -- most of the record sits in the
    edge-shrunk regime below -- so callers on that leg typically pass a
    shorter window than the ramp-up/ramp-down legs use.
    """
    half = window // 2
    out = np.full_like(values, np.nan, dtype=float)
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out[i] = np.mean(values[lo:hi])
    return out


_running_mean = running_mean  # internal alias, kept for in-module call sites


def _pava_isotonic(y):
    """Pool-adjacent-violators isotonic (non-decreasing) regression.
    Standard PAVA algorithm (Ayer et al., 1955; Barlow et al., 1972).


    Minimal dependency-free implementation. Returns a monotone-increasing
    fit to y of the same length.
    """
    y = np.asarray(y, float)
    n = len(y)
    vals = list(y)
    # expand blocks back to length n, tracking block sizes
    blk_val, blk_size = [], []
    for v in vals:
        cur_v, cur_n = v, 1
        while blk_val and blk_val[-1] > cur_v:
            pv, pn = blk_val.pop(), blk_size.pop()
            cur_v = (pv * pn + cur_v * cur_n) / (pn + cur_n)
            cur_n = pn + cur_n
        blk_val.append(cur_v)
        blk_size.append(cur_n)
    out = np.empty(n)
    idx = 0
    for v, sz in zip(blk_val, blk_size):
        out[idx : idx + sz] = v
        idx += sz
    return out


def axis_variable(
    years,
    anom,
    method="running_mean",
    window=31,
    return_intermediate=False,
    direction="increasing",
):
    """Build a monotone temperature axis T~(t) from the anomaly.

    method:
      'running_mean'   : 31-yr centred mean, then enforce monotonicity by
                         isotonic (PAVA) regression. Matches how the protocol
                         diagnoses GWL crossings.
      'monotone_spline': isotonic regression on the raw annual anomaly
                         (no pre-smoothing); stiffer, keeps more of the
                         transient shape.
      'cummax'         : running mean then cumulative max (crude, unambiguous).

    direction:
      'increasing' (default) : ramp-up leg, GMSAT is warming; T~ is monotone
                         non-decreasing.
      'decreasing'    : ramp-down leg, GMSAT is cooling; T~ is monotone
                         non-increasing. Implemented by negating the series,
                         applying the same increasing-case logic, and negating
                         back, so the two directions share one PAVA/cummax
                         implementation.

    Only applies the monotonic fix *within* one leg's own anomaly series.
    Do not run this across a full up+hold+down trajectory: GWL is not
    monotonic over that combined span (it rises, plateaus, then falls), and
    forcing it to be would erase the very hysteresis/path-dependence the
    ramp-down leg exists to preserve.

    Returns T~ (monotone in the requested direction). If return_intermediate,
    also returns the pre-monotonization series, so callers can isolate how
    much the monotonization step (not the smoothing) actually changed.
    """
    if direction not in ("increasing", "decreasing"):
        raise ValueError(f"Unknown direction '{direction}'.")
    sign = 1.0 if direction == "increasing" else -1.0

    if method == "running_mean":
        pre = _running_mean(years, anom, window)
        T = sign * _pava_isotonic(sign * pre)
    elif method == "monotone_spline":
        pre = anom.copy()
        T = sign * _pava_isotonic(sign * anom)
    elif method == "cummax":
        pre = _running_mean(years, anom, window)
        T = sign * np.maximum.accumulate(sign * pre)
    else:
        raise ValueError(f"Unknown method '{method}'.")
    return (T, pre) if return_intermediate else T


def monotonicity_report(anom_raw, T_pre, T_axis):
    """Diagnostic: separate the smoothing adjustment from the monotonization.

    * smoothing_rms   : how much the smoothing step moved the series off the
                        raw annual anomaly (expected ~interannual scale).
    * monotonization_max : max |T_pre - T_axis|, i.e. how much enforcing
                        monotonicity changed the ALREADY-smoothed series. This
                        is the number to watch: if it is non-trivial relative
                        to your GWL bin width, the inverse is doing real work
                        in some segment and that segment should be inspected
                        (it may be a genuine plateau / early abrupt feature).
    """
    smoothing = anom_raw - T_pre
    mono = np.abs(T_pre - T_axis)
    return {
        "interannual_std_degC": float(np.nanstd(np.diff(anom_raw))),
        "smoothing_rms_degC": float(np.sqrt(np.nanmean(smoothing**2))),
        "monotonization_max_degC": float(np.nanmax(mono)),
        "frac_years_monotonized_gt_0p02": float(np.nanmean(mono > 0.02)),
    }


# ---------------------------------------------------------------------------
# Inversion t(T) and resampling onto a common grid
# ---------------------------------------------------------------------------
def invert_to_grid(years, T_axis, T_grid, direction="increasing"):
    """Invert T~(t) to t(T) on a common temperature grid.

    T_axis must be monotone in the given ``direction`` ('increasing' for the
    ramp-up leg, 'decreasing' for the ramp-down leg). Strictly monotone is
    required for a unique inverse; ties (flat segments) are nudged by a tiny
    epsilon so the interpolator is well defined. For 'decreasing', T_axis and
    T_grid are negated before inversion (making them increasing for
    PchipInterpolator) and the looked-up years are returned as-is -- negation
    only touches the temperature values, never the years. Values of T_grid
    outside the model's realized range return NaN (model never reached that
    GWL on this leg).
    """
    if direction not in ("increasing", "decreasing"):
        raise ValueError(f"Unknown direction '{direction}'.")
    sign = 1.0 if direction == "increasing" else -1.0

    T = sign * np.asarray(T_axis, float).copy()
    # break exact ties to make strictly increasing
    eps = 1e-9
    for i in range(1, len(T)):
        if T[i] <= T[i - 1]:
            T[i] = T[i - 1] + eps
    inv = PchipInterpolator(T, years, extrapolate=False)
    t_of_T = inv(sign * np.asarray(T_grid, float))  # NaN outside realized range
    return t_of_T


def resample_variable(years, var, t_of_T):
    """Interpolate an arbitrary variable(time) onto the temperature grid.

    Linear interpolation in time (axis noise already handled when building the
    axis). NaNs in t_of_T (unreached GWLs) propagate to the output.
    """
    out = np.full_like(t_of_T, np.nan, dtype=float)
    good = np.isfinite(t_of_T)
    out[good] = np.interp(t_of_T[good], years, var)
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

GWL_GRID_STEP = 0.02  # degC; one year at the protocol's nominal 2 degC/century rate
RAMP_UP_GWL_MIN = 0.0
RAMP_UP_GWL_MAX = 4.0
RAMP_DOWN_GWL_MIN = -2.0
RAMP_DOWN_GWL_MAX = 5.0


def gwl_grid(
    step: float = GWL_GRID_STEP, gwl_max: float = 4.0, gwl_min: float = 0.0
) -> np.ndarray:
    """Build a common GWL coordinate: ``gwl_min`` to ``gwl_max`` in steps of ``step`` (degC).

    Endpoints are included (e.g. ``gwl_grid()`` -> 0.00, 0.02, …, 4.00 at the
    default step). Defaults match the ramp-up leg (0-4 degC).
    """
    if step <= 0:
        raise ValueError(f"gwl step must be positive, got {step}")
    if gwl_max <= gwl_min:
        raise ValueError(
            f"gwl_max must exceed gwl_min, got gwl_max={gwl_max}, gwl_min={gwl_min}"
        )
    return np.arange(gwl_min, gwl_max + step / 2, step)


def gwl_grid_rampdown(step: float = GWL_GRID_STEP) -> np.ndarray:
    """Ramp-down common grid: ``RAMP_DOWN_GWL_MIN``…``RAMP_DOWN_GWL_MAX`` at ``step`` (degC).

    Point-aligned with ``gwl_grid()`` (ramp-up): every ramp-up grid value in
    0-4 degC appears at the same coordinate on this extended grid, so
    ``resample_to_gwl`` outputs can be differenced leg-by-leg without
    interpolation mismatch.

    Built by extending the ramp-up grid downward and upward from its endpoints
    (not a separate ``np.arange`` from ``RAMP_DOWN_GWL_MIN``), avoiding
    floating-point drift at the shared 0-4 degC points.
    """
    ramp_up = gwl_grid(
        step=step, gwl_min=RAMP_UP_GWL_MIN, gwl_max=RAMP_UP_GWL_MAX
    )
    n_below = int(round((ramp_up[0] - RAMP_DOWN_GWL_MIN) / step))
    n_above = int(round((RAMP_DOWN_GWL_MAX - ramp_up[-1]) / step))
    below = ramp_up[0] - step * np.arange(n_below, 0, -1, dtype=float)
    above = ramp_up[-1] + step * np.arange(1, n_above + 1, dtype=float)
    grid = np.concatenate([below, ramp_up, above])
    if not (
        np.isclose(grid[0], RAMP_DOWN_GWL_MIN)
        and np.isclose(grid[-1], RAMP_DOWN_GWL_MAX)
    ):
        raise RuntimeError(
            "ramp-down grid endpoints do not match configured bounds"
        )
    if not np.array_equal(ramp_up, grid[n_below : n_below + ramp_up.size]):
        raise RuntimeError("ramp-down grid is not point-aligned with ramp-up grid")
    return grid


@dataclass
class MappingConfig:
    window: int = 31
    method: str = "running_mean"
    detrend_pi: bool = False
    # Common GWL grid: 0-4 degC in 0.02 degC steps (~1 yr at 2 degC/century).
    T_grid: np.ndarray = field(default_factory=lambda: gwl_grid())
    # 'increasing' for the ramp-up leg (default), 'decreasing' for ramp-down.
    direction: str = "increasing"


@dataclass
class ModelMapping:
    name: str
    T_grid: np.ndarray
    t_of_T: np.ndarray  # year at each GWL
    anom: np.ndarray  # raw anomaly(time)
    T_axis: np.ndarray  # monotone axis(time)
    T_pre: np.ndarray  # smoothed anomaly before the monotonicity step
    years: np.ndarray
    diagnostics: dict
    resampled: dict = field(default_factory=dict)  # varname -> array on T_grid


def map_model(
    name,
    ru_years,
    ru_gmsat,
    pi_years,
    pi_gmsat,
    branch_year,
    extra_vars=None,
    cfg: MappingConfig | None = None,
    *,
    pi_reference: float | None = None,
):
    """Full per-model pipeline (paper Steps 1–3).

    Step 1: anomaly from piControl reference.
    Step 2: smooth and enforce monotonicity (:func:`axis_variable`).
    Step 3: invert onto the common GWL grid (:func:`invert_to_grid`).

    This is the single source of truth for the mapping algorithm; the CMIP-aware
    drivers (``build.build_mapping_dataset``, ``paper/helper_diagnostics.py``)
    call it rather than re-implementing the steps.

    extra_vars : dict {varname: (years, values)} to resample onto the T grid
                 (e.g. atmospheric CO2, sea-ice area, AMOC strength...).
                 If a variable shares ru_years you may pass values only by
                 wrapping as (ru_years, values).
    pi_reference : optional precomputed baseline (anomaly zero point). When given,
                 it is used directly and ``pi_years``/``pi_gmsat``/``branch_year``
                 are not consulted for the reference; pass this from
                 :func:`tipmip_gwl.baseline.compute_baseline` so the CMIP-aware
                 baseline (with drift/method/n_years) and the axis share one value.
                 When omitted, the full-run piControl mean is computed here.
    """
    cfg = cfg or MappingConfig()
    pi_ref = (
        float(pi_reference)
        if pi_reference is not None
        else picontrol_reference(
            pi_years, pi_gmsat, branch_year, detrend=cfg.detrend_pi
        )
    )
    anom = to_anomaly(ru_years, ru_gmsat, pi_ref)
    T_axis, T_pre = axis_variable(
        ru_years,
        anom,
        method=cfg.method,
        window=cfg.window,
        return_intermediate=True,
        direction=cfg.direction,
    )
    t_of_T = invert_to_grid(ru_years, T_axis, cfg.T_grid, direction=cfg.direction)
    diag = monotonicity_report(anom, T_pre, T_axis)
    diag["pi_reference_GMSAT"] = pi_ref
    diag["max_GWL_reached"] = float(np.nanmax(T_axis))
    diag["min_GWL_reached"] = float(np.nanmin(T_axis))

    mm = ModelMapping(
        name=name,
        T_grid=cfg.T_grid,
        t_of_T=t_of_T,
        anom=anom,
        T_axis=T_axis,
        T_pre=T_pre,
        years=ru_years,
        diagnostics=diag,
    )

    if extra_vars:
        for vname, (vyears, vvals) in extra_vars.items():
            # map each extra variable through ITS OWN time->grid using t_of_T
            mm.resampled[vname] = resample_variable(vyears, vvals, t_of_T)
    return mm


def stack_models(mappings, varname):
    """Stack a resampled variable across models onto the shared T grid.

    Returns (T_grid, array[n_models, n_T], names). NaN where a model never
    reached that GWL. Ready for ensemble mean / spread in temperature space.
    """
    names = [m.name for m in mappings]
    T_grid = mappings[0].T_grid
    for m in mappings:
        if not np.allclose(m.T_grid, T_grid):
            raise ValueError("Models use different T grids; re-run with one cfg.")
    stack = np.vstack([m.resampled[varname] for m in mappings])
    return T_grid, stack, names


# ---------------------------------------------------------------------------
# Sensitivity matrix
# ---------------------------------------------------------------------------
def sensitivity_matrix(
    name,
    ru_years,
    ru_gmsat,
    pi_years,
    pi_gmsat,
    branch_year,
    target_var,
    windows=(21, 31, 41),
    methods=("running_mean", "monotone_spline"),
    detrend_opts=(False, True),
    T_grid=None,
    direction="increasing",
):
    """Re-run the mapping over a grid of methodological choices for one model.

    Returns dict keyed by (window, method, detrend) -> target_var on T_grid.
    Use this to check whether a headline multi-model result is stable, or
    whether 'spread at 1.5 degC' is partly a methods artifact.
    """
    T_grid = gwl_grid() if T_grid is None else T_grid
    results = {}
    for w in windows:
        for meth in methods:
            for dt in detrend_opts:
                cfg = MappingConfig(
                    window=w,
                    method=meth,
                    detrend_pi=dt,
                    T_grid=T_grid,
                    direction=direction,
                )
                mm = map_model(
                    name,
                    ru_years,
                    ru_gmsat,
                    pi_years,
                    pi_gmsat,
                    branch_year,
                    extra_vars={"target": (ru_years, target_var)},
                    cfg=cfg,
                )
                results[(w, meth, dt)] = mm.resampled["target"]
    return results
