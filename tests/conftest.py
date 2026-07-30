"""Pytest configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
MAPPINGS_DIR = REPO_ROOT.parent / "tipmip-gwl-mappings"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if MAPPINGS_DIR.is_dir():
    os.environ.setdefault("TIPMIP_GWL_MAPPINGS", str(MAPPINGS_DIR))

requires_mappings = pytest.mark.skipif(
    not MAPPINGS_DIR.is_dir(),
    reason="tipmip-gwl-mappings sibling clone required (see README.md)",
)
