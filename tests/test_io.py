"""Tests for filename discovery helpers."""

from tipmip_gwl.io import model_from_filename, model_label


def test_model_from_filename():
    name = "tas_Amon_UKESM1-2-LL_esm-up2p0_r1i1p1f1_gn_gmstmon.nc"
    assert model_from_filename(name) == "UKESM1-2-LL"


def test_model_label_prefers_model_id():
    assert model_label({"model_id": "UKESM1-2-LL", "source_id": "eUKESM1-1-ice-N96ORCA1"}) == "UKESM1-2-LL"


def test_model_label_from_rampup_file():
    attrs = {
        "source_id": "eUKESM1-1-ice-N96ORCA1",
        "rampup_file": "tas_Amon_UKESM1-2-LL_esm-up2p0_r1i1p1f1_gn_gmstmon.nc",
    }
    assert model_label(attrs) == "UKESM1-2-LL"
