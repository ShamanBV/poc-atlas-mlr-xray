"""
Pytest fixtures shared across the test suite.

Why this exists: `mlr.precheck.api` triggers a library bootstrap at
import time (reading from the extractor service's eval directory).
Tests must be deterministic regardless of whether that directory is
present or what's in it — so we reset the library to its hardcoded
default before every test.

Tests that *want* the bootstrapped library can override locally by
calling `library.set_library(...)` after the autouse fixture runs.
"""

from __future__ import annotations

import pytest

from mlr.precheck import library


@pytest.fixture(autouse=True)
def _reset_library() -> None:
    """Restore the hardcoded library before each test."""
    library.reset_library()
