"""
mapping.py
==========
Pure (numpy/scipy) re-indexing of a time series onto a common TEMPERATURE
(GMSAT-anomaly) axis, so models can be stacked and compared at a common global
warming level (GWL) rather than at a common year.

This module is deliberately free of any file-format or CMIP knowledge: it works
on plain (years, values) arrays. The TIPMIP/NetCDF-specific glue lives in
:mod:`tipmip_gwl.tipmip`.

Scope / assumptions
-------------------
* Designed for the *ramp-up* leg (esm-up2p0). On a single monotonic warming
  path, temperature-matching is well posed. Do NOT reuse the resulting axis to
  equate a ramp-up state with a ramp-down state at the same GWL: same GWL on
  different paths is a different Earth-system state. That path-dependence is a
  science target, not a nuisance to interpolate away.
* Baseline (the zero of the anomaly) is the mean of the model's OWN piControl
  GMSAT over the full control run.

Dependencies: numpy, scipy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator


# ---------------------------------------------------------------------------
# I/O (generic ASCII helper; NetCDF loading lives in tipmip_gwl.tipmip)
# ---------------------------------------------------------------------------
def load_series(path, year_col=0, value_col=1, comments="#"):
    """Load a (year, value) ASCII series. Returns (years, values) float arrays.

    Adjust column indices / delimiter to the real file format.
    """
    raw = np.genfromtxt(path, comments=comments)
    if raw.ndim == 1:  # single row safety
        raw = raw[None, :]
    years = raw[:, year_col].astype(float)
    vals = raw[:, value_col].astype(float)
    order = np.argsort(years)
    return years[order], vals[order]


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
def _running_mean(years, values, window):
    """Centred running mean on a (assumed) 1-year cadence. Edges shrink window."""
    half = window // 2
    out = np.full_like(values, np.nan, dtype=float)
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out[i] = np.mean(values[lo:hi])
    return out


def _pava_isotonic(y):
    """Pool-adjacent-violators isotonic (non-decreasing) regression.

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
    years, anom, method="running_mean", window=31, return_intermediate=False
):
    """Build a monotone-increasing temperature axis T~(t) from the anomaly.

    method:
      'running_mean'   : 31-yr centred mean, then enforce monotonicity by
                         isotonic (PAVA) regression. Matches how the protocol
                         diagnoses GWL crossings.
      'monotone_spline': isotonic regression on the raw annual anomaly
                         (no pre-smoothing); stiffer, keeps more of the
                         transient shape.
      'cummax'         : running mean then cumulative max (crude, unambiguous).

    Returns T~ (monotone non-decreasing). If return_intermediate, also returns
    the pre-monotonization series, so callers can isolate how much the
    monotonization step (not the smoothing) actually changed.
    """
    if method == "running_mean":
        pre = _running_mean(years, anom, window)
        T = _pava_isotonic(pre)
    elif method == "monotone_spline":
        pre = anom.copy()
        T = _pava_isotonic(anom)
    elif method == "cummax":
        pre = _running_mean(years, anom, window)
        T = np.maximum.accumulate(pre)
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
def invert_to_grid(years, T_axis, T_grid):
    """Invert T~(t) to t(T) on a common temperature grid.

    T_axis must be monotone non-decreasing. Strictly increasing is required for
    a unique inverse; ties (flat segments) are nudged by a tiny epsilon so the
    interpolator is well defined. Values of T_grid outside the model's realized
    range return NaN (model never reached that GWL on this leg).
    """
    T = np.asarray(T_axis, float).copy()
    # break exact ties to make strictly increasing
    eps = 1e-9
    for i in range(1, len(T)):
        if T[i] <= T[i - 1]:
            T[i] = T[i - 1] + eps
    inv = PchipInterpolator(T, years, extrapolate=False)
    t_of_T = inv(T_grid)  # NaN outside [T.min(), T.max()]
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

def gwl_grid(step: float = 0.1, gwl_max: float = 4.0) -> np.ndarray:
    """Build the common GWL coordinate: 0 to ``gwl_max`` in steps of ``step`` (degC).

    Endpoints are included (e.g. ``gwl_grid(0.1)`` -> 0.0, 0.1, …, 4.0).
    """
    if step <= 0:
        raise ValueError(f"gwl step must be positive, got {step}")
    if gwl_max < 0:
        raise ValueError(f"gwl_max must be non-negative, got {gwl_max}")
    return np.arange(0.0, gwl_max + step / 2, step)


@dataclass
class MappingConfig:
    window: int = 31
    method: str = "running_mean"
    detrend_pi: bool = False
    # Common GWL grid: 0-4 degC in 0.1 steps. All clean models reach ~4 degC;
    # above that the ensemble thins and values beyond a model's range are NaN.
    T_grid: np.ndarray = field(default_factory=lambda: gwl_grid())


@dataclass
class ModelMapping:
    name: str
    T_grid: np.ndarray
    t_of_T: np.ndarray  # year at each GWL
    anom: np.ndarray  # raw anomaly(time)
    T_axis: np.ndarray  # monotone axis(time)
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
):
    """Full per-model pipeline: anomaly -> monotone axis -> t(T) -> resample.

    extra_vars : dict {varname: (years, values)} to resample onto the T grid
                 (e.g. atmospheric CO2, sea-ice area, AMOC strength...).
                 If a variable shares ru_years you may pass values only by
                 wrapping as (ru_years, values).
    """
    cfg = cfg or MappingConfig()
    pi_ref = picontrol_reference(
        pi_years, pi_gmsat, branch_year, detrend=cfg.detrend_pi
    )
    anom = to_anomaly(ru_years, ru_gmsat, pi_ref)
    T_axis, T_pre = axis_variable(
        ru_years, anom, method=cfg.method, window=cfg.window, return_intermediate=True
    )
    t_of_T = invert_to_grid(ru_years, T_axis, cfg.T_grid)
    diag = monotonicity_report(anom, T_pre, T_axis)
    diag["pi_reference_GMSAT"] = pi_ref
    diag["max_GWL_reached"] = float(np.nanmax(T_axis))

    mm = ModelMapping(
        name=name,
        T_grid=cfg.T_grid,
        t_of_T=t_of_T,
        anom=anom,
        T_axis=T_axis,
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
):
    """Re-run the mapping over a grid of methodological choices for one model.

    Returns dict keyed by (window, method, detrend) -> target_var on T_grid.
    Use this to check whether a headline multi-model result is stable, or
    whether 'spread at 1.5 degC' is partly a methods artifact.
    """
    T_grid = np.arange(0.0, 4.0001, 0.1) if T_grid is None else T_grid
    results = {}
    for w in windows:
        for meth in methods:
            for dt in detrend_opts:
                cfg = MappingConfig(window=w, method=meth, detrend_pi=dt, T_grid=T_grid)
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
