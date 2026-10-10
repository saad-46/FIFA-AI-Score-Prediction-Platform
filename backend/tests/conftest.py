"""
Shared fixtures.

The API serves predictions from the engine named by ``PREDICTION_ENGINE``
("legacy" by default, "v3" as an explicit opt-in). Tests ask for the engine
they are about -- ``legacy_engine`` or ``v3_engine`` -- so they do not depend
on the default or on whatever a local .env sets.
"""

import pytest

from app.core.config import get_settings
from app.ml.model_loader import reset_model_loader


def _set_engine(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PREDICTION_ENGINE", raising=False)
    else:
        monkeypatch.setenv("PREDICTION_ENGINE", value)
    get_settings.cache_clear()
    reset_model_loader()


@pytest.fixture
def legacy_engine(monkeypatch):
    """Serve from the existing (pre-V3) predictor for the duration of a test."""
    _set_engine(monkeypatch, "legacy")
    yield
    _set_engine(monkeypatch, None)


@pytest.fixture
def v3_engine(monkeypatch):
    """Serve from the V3 pipeline regardless of the local environment."""
    _set_engine(monkeypatch, "v3")
    yield
    _set_engine(monkeypatch, None)
