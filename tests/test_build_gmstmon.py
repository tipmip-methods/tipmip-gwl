"""Tests for gmstmon build helpers (scripts/build_gmstmon.py)."""

from __future__ import annotations

import numpy as np
import xarray as xr

from build_gmstmon import _dedupe_monthly_time, load_tas_chunks


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


def test_load_tas_chunks_accepts_noresm_swl_alias(tmp_path):
    manifest = tmp_path / "chunks.tsv"
    manifest.write_text(
        "model\texperiment_id\tpath\n"
        "NorESM2-LM\tesm-up2p0-swl2p0-50y-dn2p0\t"
        "/data/tas_Amon_NorESM2-LM_esm-up2p0-swl2p0-50y-dn2p0_r1i1p1f1_gn_200101-200912.nc\n"
    )
    chunks = load_tas_chunks(manifest, "esm-up2p0-gwl2p0-50y-dn2p0")
    assert "NorESM2-LM" in chunks
    assert len(chunks["NorESM2-LM"]) == 1

