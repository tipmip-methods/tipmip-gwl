"""Shared colours and model ordering for paper figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from tipmip_gwl.io import discover, load_gmsat_nc

MODEL_PALETTE = plt.cm.Dark2.colors


def model_color_map(models: list[str]) -> dict[str, str]:
    """Stable Dark2 colour per model (canonical order: alphabetical).

    Used by ``mapping_axis_up_down.png``, ``baseline_reference_comparison.png``,
    and ``paper/figures_1_2.py`` for ``picontrol_baseline.png``.
    """
    ordered = sorted(dict.fromkeys(models))
    return {model: MODEL_PALETTE[i % len(MODEL_PALETTE)] for i, model in enumerate(ordered)}


def models_sorted_by_picontrol_mean(picontrol_dir: Path | str) -> list[str]:
    """Same vertical ordering as ``mean_tas_piControl.py`` (low → high piControl mean)."""
    pi_files = discover(picontrol_dir)
    entries: list[tuple[float, str]] = []
    for model, path in pi_files.items():
        _years, gmsat = load_gmsat_nc(path)
        entries.append((float(np.mean(gmsat)), model))
    entries.sort(key=lambda item: item[0])
    return [model for _mean, model in entries]
