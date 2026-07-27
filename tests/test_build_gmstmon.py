"""Tests for gmstmon build helpers (scripts/build_gmstmon.py)."""

from __future__ import annotations

import numpy as np
import xarray as xr

from build_gmstmon import _dedupe_monthly_time


def _monthly_da(values: list[float], calendar: str = "360_day") -> xr.DataArray:
    time = xr.date_range(
        "2000-01-01",
        periods=len(values) // 2,
        freq="MS",
        calendar=calendar,
        use_cftime=True,
    )
    time = xr.DataArray(list(time.values) * 2, dims=("time",))
    return xr.DataArray(values, coords={"time": time}, dims=("time",))


def test_dedupe_monthly_time_drops_identical_duplicates():
    da = _monthly_da([1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0])

    deduped, warns = _dedupe_monthly_time(da)

    assert deduped.sizes["time"] == 4
    np.testing.assert_allclose(deduped.values, [1.0, 2.0, 3.0, 4.0])
    assert warns and "identical" in warns[0]


def test_dedupe_monthly_time_flags_conflicting_duplicates():
    da = _monthly_da([1.0, 2.0, 1.5, 2.0], calendar="proleptic_gregorian")

    deduped, warns = _dedupe_monthly_time(da)

    assert deduped.sizes["time"] == 2
    np.testing.assert_allclose(deduped.values, [1.0, 2.0])
    assert warns and "differing values" in warns[0]
