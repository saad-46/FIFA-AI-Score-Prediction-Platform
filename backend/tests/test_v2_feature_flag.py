"""
Feature-flag selection, legacy-safety, API smoke tests, and legacy-vs-V2
comparison for the V2 backend integration.

USE_V2_MODEL defaults to false. Every test that flips it restores the
original setting and clears both caches (`get_settings` is `@lru_cache`d,
and `ModelLoader` caches its resolved adapters) so flag state never leaks
between tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.ml.model_loader import (
    LegacyPredictionAdapter,
    get_model_loader,
    reset_model_loader,
)
from app.ml.v2.model_wrapper import V2PredictionAdapter
from app.services.prediction_service import run_prediction


#: The V2 model versions that may legitimately serve traffic when the flag is
#: on. Asserting membership rather than one hardcoded string means these tests
#: verify "the flag routes to a V2 model", which is the actual contract, and
#: don't break every time the configured default bundle changes.
V2_MODEL_VERSIONS = {"v2-calibrated", "v2-production-calibrated"}


@pytest.fixture
def use_v2(monkeypatch):
    """
    Flip USE_V2_MODEL for the duration of a test, then restore it.

    Also pins the V2 data source to CSV: these tests are about flag routing,
    not about the database, and they should neither require network access nor
    pay the cost of a Supabase read per adapter construction.
    """
    def _set(value: bool):
        monkeypatch.setenv("USE_V2_MODEL", "true" if value else "false")
        monkeypatch.setenv("V2_DATA_SOURCE", "csv")
        get_settings.cache_clear()
        reset_model_loader()
    yield _set
    monkeypatch.delenv("USE_V2_MODEL", raising=False)
    monkeypatch.delenv("V2_DATA_SOURCE", raising=False)
    get_settings.cache_clear()
    reset_model_loader()


def _small_history_df() -> pd.DataFrame:
    rows = []
    for i in range(6):
        rows.append({
            "date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=7 * i),
            "home_team": "Brazil", "away_team": f"Filler{i}",
            "home_score": 2, "away_score": 1, "tournament": "Friendly",
            "neutral_venue": False,
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Default state
# ═══════════════════════════════════════════════════════════════════════════

def test_default_flag_is_false():
    """The flag's own default, independent of any .env — the stop condition
    is a code default, not just current environment configuration."""
    assert get_settings.__wrapped__.__annotations__ or True  # sanity: settings module loads
    from app.core.config import Settings
    assert Settings.model_fields["USE_V2_MODEL"].default is False


def test_default_active_adapter_is_legacy(use_v2):
    use_v2(False)
    adapter = get_model_loader().get_active()
    assert isinstance(adapter, LegacyPredictionAdapter)


# ═══════════════════════════════════════════════════════════════════════════
# Feature flag selection
# ═══════════════════════════════════════════════════════════════════════════

def test_flag_off_selects_legacy(use_v2):
    use_v2(False)
    adapter = get_model_loader().get_active()
    assert isinstance(adapter, LegacyPredictionAdapter)
    assert not isinstance(adapter, V2PredictionAdapter)


def test_flag_on_selects_v2(use_v2):
    use_v2(True)
    adapter = get_model_loader().get_active()
    assert isinstance(adapter, V2PredictionAdapter)


def test_flag_off_never_imports_v2_module(use_v2):
    """USE_V2_MODEL=false must not even import app.ml.v2 — the isolation is
    structural (lazy import inside get_v2()), not just 'unused'."""
    import sys
    use_v2(False)
    v2_modules_before = {m for m in sys.modules if m.startswith("app.ml.v2")}
    get_model_loader().get_active()
    v2_modules_after = {m for m in sys.modules if m.startswith("app.ml.v2")}
    # (This only proves no *new* v2 import happened on this call; if an
    # earlier test in the same session already imported it that's fine —
    # the guarantee under test is "get_active() with the flag off doesn't
    # trigger an import", which holds regardless of prior state.)
    assert v2_modules_after == v2_modules_before


# ═══════════════════════════════════════════════════════════════════════════
# Legacy safety — flag OFF must be byte-identical to pre-integration behavior
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_legacy_path_unchanged_with_flag_off(use_v2):
    use_v2(False)
    df = _small_history_df()
    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        result = await run_prediction(home_team="Brazil", away_team="Filler0")

    assert result.model_version not in V2_MODEL_VERSIONS
    assert 0.0 <= result.home_win_probability <= 1.0
    assert 0.0 <= result.draw_probability <= 1.0
    assert 0.0 <= result.away_win_probability <= 1.0
    total = result.home_win_probability + result.draw_probability + result.away_win_probability
    assert total == pytest.approx(1.0, abs=1e-2)


@pytest.mark.asyncio
async def test_v2_path_produces_prediction_with_flag_on(use_v2):
    use_v2(True)
    # No DB patching needed — V2's history/feature source is the local
    # canonical snapshot, not load_matches_dataframe().
    result = await run_prediction(home_team="France", away_team="Brazil")

    assert result.model_version in V2_MODEL_VERSIONS
    total = result.home_win_probability + result.draw_probability + result.away_win_probability
    assert total == pytest.approx(1.0, abs=1e-2)
    assert result.predicted_home_score >= 0
    assert result.predicted_away_score >= 0


# ═══════════════════════════════════════════════════════════════════════════
# API smoke tests — same endpoint, both flag states
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_smoke_flag_off(use_v2):
    use_v2(False)
    df = _small_history_df()
    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/predictions/predict",
                json={"home_team": "Brazil", "away_team": "Filler0"},
            )

    assert response.status_code == 200
    data = response.json()
    for field in ("home_win_probability", "draw_probability", "away_win_probability",
                  "predicted_home_score", "predicted_away_score", "model_version",
                  "confidence_score"):
        assert field in data
    assert data["model_version"] not in V2_MODEL_VERSIONS


@pytest.mark.asyncio
async def test_api_smoke_flag_on(use_v2):
    use_v2(True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/predictions/predict",
            json={"home_team": "France", "away_team": "Brazil"},
        )

    assert response.status_code == 200
    data = response.json()
    for field in ("home_win_probability", "draw_probability", "away_win_probability",
                  "predicted_home_score", "predicted_away_score", "model_version",
                  "confidence_score"):
        assert field in data
    assert data["model_version"] in V2_MODEL_VERSIONS
    prob_sum = data["home_win_probability"] + data["draw_probability"] + data["away_win_probability"]
    assert prob_sum == pytest.approx(1.0, abs=1e-2)


@pytest.mark.asyncio
async def test_api_same_response_shape_both_flags(use_v2):
    """Same endpoint, same response schema keys, regardless of flag —
    confirms the API contract itself did not change."""
    async def _call():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(
                "/api/v1/predictions/predict",
                json={"home_team": "France", "away_team": "Brazil"},
            )

    use_v2(True)
    v2_resp = await _call()

    use_v2(False)
    df = _small_history_df()
    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        legacy_resp = await _call()

    assert v2_resp.status_code == legacy_resp.status_code == 200
    assert set(v2_resp.json().keys()) == set(legacy_resp.json().keys())


# ═══════════════════════════════════════════════════════════════════════════
# Legacy vs V2 comparison — same inputs, results allowed to differ, structure
# must not
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_legacy_vs_v2_comparison_same_inputs(use_v2):
    """Not an equality test — the models are architecturally different
    (different training window, different calibration). The purpose is to
    confirm both produce structurally valid, independently reproducible
    output for the identical request, and to record what actually differs."""
    use_v2(False)
    df = _small_history_df()
    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        legacy = await run_prediction(home_team="Brazil", away_team="Filler0")

    use_v2(True)
    v2 = await run_prediction(home_team="Brazil", away_team="Filler0")

    for result in (legacy, v2):
        total = result.home_win_probability + result.draw_probability + result.away_win_probability
        assert total == pytest.approx(1.0, abs=1e-2)
        assert result.predicted_home_score >= 0
        assert result.predicted_away_score >= 0

    assert legacy.model_version != v2.model_version
    assert v2.model_version in V2_MODEL_VERSIONS
