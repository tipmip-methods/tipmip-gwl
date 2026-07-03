"""Tests for the pure-array mapping algorithm (no NetCDF/CMIP involved)."""

import numpy as np
import pytest

from tipmip_gwl.mapping import (
    MappingConfig,
    axis_variable,
    gwl_grid,
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


def test_gwl_grid_endpoints_included():
    grid = gwl_grid(step=0.1, gwl_max=4.0)
    assert grid[0] == 0.0
    assert grid[-1] == pytest.approx(4.0)
    assert grid.size == 41


def test_gwl_grid_rejects_bad_args():
    with pytest.raises(ValueError):
        gwl_grid(step=0.0)
    with pytest.raises(ValueError):
        gwl_grid(gwl_max=-1.0)


def test_picontrol_reference_recovers_mean():
    years = np.arange(0, 500)
    rng = np.random.default_rng(0)
    vals = 286.5 + 0.05 * rng.standard_normal(years.size)
    ref = picontrol_reference(years, vals, branch_year=250)
    assert ref == pytest.approx(np.mean(vals), abs=1e-9)


def test_picontrol_reference_detrend_anchors_at_branch_year():
    years = np.arange(0, 200, dtype=float)
    slope = 0.01
    vals = 280.0 + slope * years
    ref = picontrol_reference(years, vals, branch_year=100.0, detrend=True)
    # detrending centres the fit on branch_year, so the reference should equal
    # the (noise-free) trend value there
    assert ref == pytest.approx(280.0 + slope * 100.0, abs=1e-6)


def test_picontrol_reference_no_finite_values_raises():
    with pytest.raises(ValueError):
        picontrol_reference([1, 2, 3], [np.nan, np.nan, np.nan], branch_year=1)


def test_to_anomaly_is_a_plain_subtraction():
    gmsat = np.array([287.0, 288.0, 289.0])
    anom = to_anomaly(None, gmsat, 286.5)
    np.testing.assert_allclose(anom, [0.5, 1.5, 2.5])


def test_picontrol_drift_recovers_known_slope():
    years = np.arange(0, 1000, dtype=float)
    drift_per_year = 0.002  # -> 0.2 degC/century
    vals = 286.0 + drift_per_year * years
    out = picontrol_drift(years, vals)
    assert out["drift_degC_per_century"] == pytest.approx(0.2, abs=1e-6)
    assert out["n_years"] == years.size


def test_picontrol_drift_handles_all_nan():
    out = picontrol_drift([1, 2], [np.nan, np.nan])
    assert np.isnan(out["drift_degC_per_century"])
    assert out["n_years"] == 0


class TestAxisVariable:
    def test_running_mean_is_monotone_nondecreasing(self):
        years = np.arange(200)
        rng = np.random.default_rng(1)
        anom = 0.02 * years + 0.15 * rng.standard_normal(years.size)
        T = axis_variable(years, anom, method="running_mean", window=31)
        assert np.all(np.diff(T) >= 0)

    def test_monotone_spline_is_monotone_nondecreasing(self):
        years = np.arange(200)
        rng = np.random.default_rng(2)
        anom = 0.02 * years + 0.15 * rng.standard_normal(years.size)
        T = axis_variable(years, anom, method="monotone_spline")
        assert np.all(np.diff(T) >= 0)

    def test_cummax_is_monotone_nondecreasing(self):
        years = np.arange(200)
        rng = np.random.default_rng(3)
        anom = 0.02 * years + 0.15 * rng.standard_normal(years.size)
        T = axis_variable(years, anom, method="cummax", window=31)
        assert np.all(np.diff(T) >= 0)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            axis_variable(np.arange(10), np.zeros(10), method="bogus")

    def test_clean_linear_ramp_monotonization_does_no_work(self):
        # A clean accelerating/linear ramp is already monotone after smoothing;
        # PAVA should not need to move it (matches the paper's stated invariant).
        years = np.arange(300)
        anom = 0.02 * years  # noise-free, strictly increasing
        T, T_pre = axis_variable(
            years, anom, method="running_mean", window=31, return_intermediate=True
        )
        np.testing.assert_allclose(T, T_pre, atol=1e-10)

    def test_return_intermediate_shape(self):
        years = np.arange(50)
        anom = 0.01 * years
        T, T_pre = axis_variable(years, anom, return_intermediate=True)
        assert T.shape == T_pre.shape == years.shape


def test_monotonicity_report_flags_plateau():
    anom_raw = np.array([0.0, 0.1, 0.05, 0.2, 0.2, 0.3])
    T_pre = anom_raw.copy()
    T_axis = np.array([0.0, 0.1, 0.1, 0.2, 0.2, 0.3])  # plateau introduced at idx 2
    rep = monotonicity_report(anom_raw, T_pre, T_axis)
    assert rep["monotonization_max_degC"] == pytest.approx(0.05, abs=1e-9)
    assert rep["smoothing_rms_degC"] == 0.0


class TestInvertToGrid:
    def test_recovers_known_linear_relationship(self):
        # T(t) = 0.02 * t is exactly invertible: t(T) = T / 0.02
        years = np.arange(0, 200, dtype=float)
        T_axis = 0.02 * years
        T_grid = np.array([0.0, 0.5, 1.0, 2.0, 3.0])
        t_of_T = invert_to_grid(years, T_axis, T_grid)
        np.testing.assert_allclose(t_of_T, T_grid / 0.02, atol=1e-6)

    def test_out_of_range_grid_values_are_nan(self):
        years = np.arange(0, 50, dtype=float)
        T_axis = 0.02 * years  # max ~0.98
        t_of_T = invert_to_grid(years, T_axis, np.array([2.0, 4.0]))
        assert np.all(np.isnan(t_of_T))

    def test_flat_segments_do_not_crash(self):
        years = np.arange(0, 10, dtype=float)
        T_axis = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 3], dtype=float)
        t_of_T = invert_to_grid(years, T_axis, np.array([0.5, 1.5, 2.5]))
        assert np.all(np.isfinite(t_of_T))


def test_resample_variable_linear_interp_and_nan_propagation():
    years = np.array([0.0, 1.0, 2.0, 3.0])
    var = np.array([10.0, 20.0, 30.0, 40.0])
    t_of_T = np.array([0.5, 1.5, np.nan])
    out = resample_variable(years, var, t_of_T)
    np.testing.assert_allclose(out[:2], [15.0, 25.0])
    assert np.isnan(out[2])


def _synthetic_series(rng):
    pi_years = np.arange(1, 701)
    pi_gmsat = 286.5 + 0.12 * rng.standard_normal(pi_years.size)
    branch_year = 350
    ru_years = np.arange(branch_year, branch_year + 220)
    t = ru_years - branch_year
    true_anom = 0.02 * t
    ru_gmsat = 286.5 + true_anom + 0.13 * rng.standard_normal(t.size)
    return pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat


class TestMapModelEndToEnd:
    def test_recovers_baseline_and_monotone_axis(self):
        rng = np.random.default_rng(42)
        pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat = _synthetic_series(rng)
        cfg = MappingConfig(window=31, T_grid=np.arange(0.0, 2.0001, 0.1))
        mm = map_model(
            "SYNTH", ru_years, ru_gmsat, pi_years, pi_gmsat, branch_year, cfg=cfg
        )
        assert mm.diagnostics["pi_reference_GMSAT"] == pytest.approx(286.5, abs=0.02)
        assert np.all(np.diff(mm.T_axis) >= 0)
        assert mm.T_pre.shape == mm.T_axis.shape

    def test_precomputed_pi_reference_is_used_verbatim(self):
        rng = np.random.default_rng(7)
        pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat = _synthetic_series(rng)
        mm = map_model(
            "SYNTH",
            ru_years,
            ru_gmsat,
            pi_years,
            pi_gmsat,
            branch_year,
            pi_reference=100.0,
        )
        # anomaly should be ru_gmsat - 100.0 exactly, regardless of pi_gmsat
        np.testing.assert_allclose(mm.anom, ru_gmsat - 100.0)
        assert mm.diagnostics["pi_reference_GMSAT"] == 100.0

    def test_extra_vars_resampled_onto_grid(self):
        rng = np.random.default_rng(11)
        pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat = _synthetic_series(rng)
        co2 = 285.0 + 4.0 * (ru_years - branch_year)
        cfg = MappingConfig(T_grid=np.arange(0.0, 2.0001, 0.5))
        mm = map_model(
            "SYNTH",
            ru_years,
            ru_gmsat,
            pi_years,
            pi_gmsat,
            branch_year,
            extra_vars={"atmCO2": (ru_years, co2)},
            cfg=cfg,
        )
        assert "atmCO2" in mm.resampled
        assert mm.resampled["atmCO2"].shape == mm.T_grid.shape


def test_stack_models_requires_matching_grid():
    rng = np.random.default_rng(3)
    pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat = _synthetic_series(rng)
    cfg_a = MappingConfig(T_grid=np.arange(0.0, 1.0001, 0.5))
    cfg_b = MappingConfig(T_grid=np.arange(0.0, 2.0001, 0.5))
    mm_a = map_model(
        "A",
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch_year,
        extra_vars={"x": (ru_years, ru_gmsat)},
        cfg=cfg_a,
    )
    mm_b = map_model(
        "B",
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch_year,
        extra_vars={"x": (ru_years, ru_gmsat)},
        cfg=cfg_b,
    )
    with pytest.raises(ValueError):
        stack_models([mm_a, mm_b], "x")


def test_sensitivity_matrix_uses_default_gwl_grid():
    rng = np.random.default_rng(5)
    pi_years, pi_gmsat, branch_year, ru_years, ru_gmsat = _synthetic_series(rng)
    results = sensitivity_matrix(
        "SYNTH",
        ru_years,
        ru_gmsat,
        pi_years,
        pi_gmsat,
        branch_year,
        target_var=ru_gmsat,
        windows=(31,),
        methods=("running_mean",),
        detrend_opts=(False,),
    )
    ((key, arr),) = results.items()
    assert key == (31, "running_mean", False)
    np.testing.assert_allclose(arr.shape[0], gwl_grid().size)
