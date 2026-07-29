"""Shared colours and model ordering for paper figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from tipmip_gwl.io import discover, load_gmsat_nc

MODEL_PALETTE = plt.cm.Dark2.colors

# Canonical Tier-1 ensemble (alphabetical). Colours are stable across figures
# even when a plot shows only one or a subset of models.
TIER1_MODELS: tuple[str, ...] = (
    "ACCESS-ESM1-5",
    "EC-Earth3-ESM-1",
    "GFDL-ESM2M",
    "GISS-E2-1-G-CC2",
    "IPSL-CM6-ESMCO2",
    "MIROC-ES2L",
    "NorESM2-LM",
    "UKESM1-2-LL",
)

_TIER1_COLOR_LOOKUP = {
    model: MODEL_PALETTE[i % len(MODEL_PALETTE)]
    for i, model in enumerate(TIER1_MODELS)
}


def model_color_map(models: list[str]) -> dict[str, str]:
    """Stable Dark2 colour per model (canonical Tier-1 order).

    Used by ``mapping_axis_up_down.png``, ``baseline_reference_comparison.png``,
    ``picontrol_baseline.png``, and diagnostic-remap figures. Unknown model ids
    fall back to unused palette slots in sorted order.
    """
    ordered = sorted(dict.fromkeys(models))
    out: dict[str, str] = {}
    fallback_i = 0
    for model in ordered:
        if model in _TIER1_COLOR_LOOKUP:
            out[model] = _TIER1_COLOR_LOOKUP[model]
        else:
            while fallback_i < len(MODEL_PALETTE) and MODEL_PALETTE[fallback_i] in out.values():
                fallback_i += 1
            out[model] = MODEL_PALETTE[fallback_i % len(MODEL_PALETTE)]
            fallback_i += 1
    return out


def models_sorted_by_picontrol_mean(picontrol_dir: Path | str) -> list[str]:
    """Same vertical ordering as ``mean_tas_piControl.py`` (low → high piControl mean)."""
    pi_files = discover(picontrol_dir)
    entries: list[tuple[float, str]] = []
    for model, path in pi_files.items():
        _years, gmsat = load_gmsat_nc(path)
        entries.append((float(np.mean(gmsat)), model))
    entries.sort(key=lambda item: item[0])
    return [model for _mean, model in entries]
