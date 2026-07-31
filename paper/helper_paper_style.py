"""Shared colours and model ordering for paper figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from tipmip_gwl.ensemble import INCLUDED_MODELS
from tipmip_gwl.io import discover, load_gmsat_nc

MODEL_PALETTE = plt.cm.Dark2.colors + ("#e41a1c",)  # Dark2 (8) + one extra (red) for a 9th model

# Alias for paper scripts; canonical list lives in tipmip_gwl.ensemble.
TIER1_MODELS = INCLUDED_MODELS

# Fixed assignment order -- NOT derived from INCLUDED_MODELS' (alphabetical)
# order. Colours are cited by name in the paper (e.g. "GFDL-ESM2M, purple";
# "MIROC-ES2L, gold"); a newly added model must get an unused colour appended
# here rather than shifting everyone else's index.
_TIER1_COLOR_ORDER: tuple[str, ...] = (
    "ACCESS-ESM1-5",
    "EC-Earth3-ESM-1",
    "GFDL-ESM2M",
    "GISS-E2-1-G-CC2",
    "IPSL-CM6-ESMCO2",
    "MIROC-ES2L",
    "NorESM2-LM",
    "UKESM1-2-LL",
    "CESM2",
)
assert set(_TIER1_COLOR_ORDER) == set(INCLUDED_MODELS), (
    "_TIER1_COLOR_ORDER (helper_paper_style.py) is out of sync with "
    "INCLUDED_MODELS (ensemble.py) -- add new models to both, appending "
    "a colour rather than reordering."
)

_TIER1_COLOR_LOOKUP = {
    model: MODEL_PALETTE[i % len(MODEL_PALETTE)]
    for i, model in enumerate(_TIER1_COLOR_ORDER)
}


def model_color_map(models: list[str]) -> dict[str, str]:
    """Stable Dark2 colour per model (canonical Tier-1 order).

    Used by ``fig_mapping_axis_up_down.png``, ``fig_baseline_reference_comparison.png``,
    ``fig_picontrol_baseline.png``, and ``fig_remap_*.png`` figures. Unknown model ids
    fall back to unused palette slots in sorted order.
    """
    ordered = sorted(dict.fromkeys(models))
    out: dict[str, str] = {}
    fallback_i = 0
    for model in ordered:
        if model in _TIER1_COLOR_LOOKUP:
            out[model] = _TIER1_COLOR_LOOKUP[model]
        else:
            while (
                fallback_i < len(MODEL_PALETTE)
                and MODEL_PALETTE[fallback_i] in out.values()
            ):
                fallback_i += 1
            out[model] = MODEL_PALETTE[fallback_i % len(MODEL_PALETTE)]
            fallback_i += 1
    return out


def models_sorted_by_picontrol_mean(picontrol_dir: Path | str) -> list[str]:
    """Same vertical ordering as ``fig_baseline_reference_comparison.py`` (low → high piControl mean)."""
    pi_files = discover(picontrol_dir)
    entries: list[tuple[float, str]] = []
    for model, path in pi_files.items():
        _years, gmsat = load_gmsat_nc(path)
        entries.append((float(np.mean(gmsat)), model))
    entries.sort(key=lambda item: item[0])
    return [model for _mean, model in entries]
