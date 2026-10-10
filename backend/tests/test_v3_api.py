"""
V3 behind the API: bundle validation, the prediction adapter, and the
/predictions/predict and /tournament/simulate endpoints.

The rate limiter is stubbed out: these tests are about the forecasting path,
and must neither depend on the database nor spend the real simulation budget.
"""

from __future__ import annotations

import json
import shutil
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.ml.model_loader import LegacyPredictionAdapter, V3PredictionAdapter, get_model_loader
from app.ml.v3 import inference, wc2026
from app.ml.v3.inference import ForecastService, ModelUnavailable, UnknownTeam, get_service, tier_for
from app.services import tournament_forecast

PREDICT = "/api/v1/predictions/predict"
SIMULATE = "/api/v1/tournament/simulate"


@pytest.fixture
def client(v3_engine):
    with patch("app.api.v1.endpoints.predictions.check_rate_limit", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.tournament.check_rate_limit", new_callable=AsyncMock):
        yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120)


@pytest.fixture
def artifacts_copy(tmp_path, monkeypatch):
    """A private copy of the artifact directory that a test may damage."""
    dst = tmp_path / "artifacts"
    shutil.copytree(inference.ART, dst)
    monkeypatch.setattr(inference, "ART", dst)
    inference.reset_services()
    yield dst
    inference.reset_services()


# ═══════════════════════════════════════════════════════════════════════════
# Engine selection and rollback
# ═══════════════════════════════════════════════════════════════════════════

def test_default_engine_is_legacy_and_v3_is_opt_in():
    assert Settings.model_fields["PREDICTION_ENGINE"].default == "legacy"
    assert Settings.model_fields["USE_V2_MODEL"].default is False


def test_unrecognised_engine_value_falls_back_to_legacy(monkeypatch):
    from app.core.config import get_settings
    from app.ml.model_loader import reset_model_loader
    monkeypatch.setenv("PREDICTION_ENGINE", "something-else")
    get_settings.cache_clear(); reset_model_loader()
    try:
        assert isinstance(get_model_loader().get_active(), LegacyPredictionAdapter)
    finally:
        monkeypatch.delenv("PREDICTION_ENGINE")
        get_settings.cache_clear(); reset_model_loader()


def test_engine_setting_selects_the_adapter(v3_engine):
    assert isinstance(get_model_loader().get_active(), V3PredictionAdapter)


def test_legacy_engine_is_still_reachable(legacy_engine):
    """The default path: without the opt-in, the existing predictor serves."""
    assert isinstance(get_model_loader().get_active(), LegacyPredictionAdapter)


# ═══════════════════════════════════════════════════════════════════════════
# Bundle validation: a bundle that cannot be verified is not served
# ═══════════════════════════════════════════════════════════════════════════

def test_active_bundle_loads_and_matches_its_manifest():
    svc = get_service()
    m = svc.manifest
    assert m["feature_schema"] == inference.SCHEMA_VERSION
    assert tuple(m["features"]) == tuple(inference.FEATURE_NAMES)
    assert inference.file_sha256(inference.ART / m["artifact"]) == m["artifact_sha256"]
    assert m["corpus_fingerprint"] == inference.corpus_fingerprint()
    assert svc.version.startswith("v3.")
    for key in ("information_cutoff", "rating_config", "source", "model"):
        assert key in m


def test_missing_bundle_is_unavailable_not_guessed(artifacts_copy):
    (artifacts_copy / "model_current.joblib").unlink()
    with pytest.raises(ModelUnavailable):
        ForecastService.load("current")


def test_missing_active_pointer_is_unavailable(artifacts_copy):
    (artifacts_copy / "ACTIVE.json").unlink()
    with pytest.raises(ModelUnavailable):
        ForecastService.load()


def test_corrupted_bundle_fails_its_checksum(artifacts_copy):
    path = artifacts_copy / "model_current.joblib"
    blob = bytearray(path.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    path.write_bytes(bytes(blob))
    with pytest.raises(ModelUnavailable, match="checksum"):
        ForecastService.load("current")


@pytest.mark.parametrize("field,value,message", [
    ("feature_schema", "v3-features-0", "feature schema"),
    ("features", ["elo_diff"], "feature schema"),
    ("corpus_fingerprint", "0000000000000000", "corpus"),
])
def test_schema_or_data_mismatch_is_refused(artifacts_copy, field, value, message):
    path = artifacts_copy / "manifest_current.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelUnavailable, match=message):
        ForecastService.load("current")


# ═══════════════════════════════════════════════════════════════════════════
# Service and adapter
# ═══════════════════════════════════════════════════════════════════════════

def test_service_prediction_shape_and_validity():
    out = get_service().predict("Spain", "Argentina", venue=0, tier=5)
    total = out["team_a_win_probability"] + out["draw_probability"] + out["team_b_win_probability"]
    assert total == pytest.approx(1.0, abs=1e-9)
    assert out["expected_goals_a"] > 0 and out["expected_goals_b"] > 0
    probs = [s["probability"] for s in out["top_scorelines"]]
    assert probs == sorted(probs, reverse=True) and sum(probs) <= 1.0 + 1e-9
    assert out["most_likely_score"] == out["top_scorelines"][0]["score"]
    assert out["information_cutoff"] and out["data_through"] < out["information_cutoff"]
    assert out["explanation"]["method"].startswith("TreeSHAP")


def test_unknown_team_and_self_match_are_rejected():
    svc = get_service()
    with pytest.raises(UnknownTeam):
        svc.predict("Atlantis FC", "Spain")
    with pytest.raises(ValueError):
        svc.predict("Spain", "Spain")


def test_tier_mapping_from_api_tournament_field():
    assert tier_for(None) == 5 and tier_for("") == 5
    assert tier_for("FIFA World Cup") == 5 and tier_for("world cup") == 5
    assert tier_for("UEFA Euro") == 4
    assert tier_for("Friendly") == 1


@pytest.mark.asyncio
async def test_adapter_honours_the_legacy_output_contract(v3_engine):
    adapter = get_model_loader().get_active()
    df = await adapter.get_history_dataframe()
    assert {"home_team", "away_team", "home_score", "away_score", "neutral_venue", "date"} <= set(df.columns)
    out = adapter.predict(df, "France", "Brazil", tournament="FIFA World Cup", neutral_venue=True)
    assert set(out) == {"expected_home_goals", "expected_away_goals", "home_win_probability", "draw_probability",
                        "away_win_probability", "most_likely_score", "top_scorelines", "prediction_explanation",
                        "confidence_score", "model_version"}
    assert out["home_win_probability"] + out["draw_probability"] + out["away_win_probability"] == pytest.approx(1.0, abs=2e-4)
    expl = out["prediction_explanation"]
    assert expl["predicted_outcome"] in {"Home Win", "Draw", "Away Win"}
    best = max(out["home_win_probability"], out["draw_probability"], out["away_win_probability"])
    assert expl["confidence"] == pytest.approx(best)
    assert 0.0 < out["confidence_score"] <= 0.95
    for item in expl["top_positive_features"] + expl["top_negative_features"]:
        assert set(item) == {"feature", "readable_name", "impact"}


# ═══════════════════════════════════════════════════════════════════════════
# POST /predictions/predict
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_predict_endpoint_response_schema(client):
    async with client as c:
        r = await c.post(PREDICT, json={"home_team": "France", "away_team": "Brazil", "neutral_venue": True})
    assert r.status_code == 200
    d = r.json()
    for field in ("prediction_id", "home_team", "away_team", "predicted_home_score", "predicted_away_score",
                  "expected_home_goals", "expected_away_goals", "home_win_probability", "draw_probability",
                  "away_win_probability", "most_likely_score", "top_scorelines", "prediction_explanation",
                  "confidence_score", "model_version", "insights", "head_to_head"):
        assert field in d
    assert d["model_version"].startswith("v3.")
    assert d["home_win_probability"] + d["draw_probability"] + d["away_win_probability"] == pytest.approx(1.0, abs=2e-4)
    assert f'{d["predicted_home_score"]}-{d["predicted_away_score"]}' == d["most_likely_score"]


@pytest.mark.asyncio
async def test_predict_endpoint_is_order_invariant_at_a_neutral_venue(client):
    async with client as c:
        ab = (await c.post(PREDICT, json={"home_team": "USA", "away_team": "Spain", "neutral_venue": True})).json()
        ba = (await c.post(PREDICT, json={"home_team": "Spain", "away_team": "USA", "neutral_venue": True})).json()
    assert ab["home_win_probability"] == pytest.approx(ba["away_win_probability"], abs=1e-4)
    assert ab["draw_probability"] == pytest.approx(ba["draw_probability"], abs=1e-4)
    assert ab["expected_home_goals"] == pytest.approx(ba["expected_away_goals"], abs=1e-3)


@pytest.mark.asyncio
async def test_predict_endpoint_gives_home_advantage_only_when_not_neutral(client):
    async with client as c:
        home = (await c.post(PREDICT, json={"home_team": "Japan", "away_team": "Brazil"})).json()
        neutral = (await c.post(PREDICT, json={"home_team": "Japan", "away_team": "Brazil", "neutral_venue": True})).json()
    assert home["home_win_probability"] > neutral["home_win_probability"]


@pytest.mark.asyncio
async def test_predict_endpoint_refuses_unknown_team(client):
    async with client as c:
        r = await c.post(PREDICT, json={"home_team": "Atlantis FC", "away_team": "Spain"})
    assert r.status_code == 422
    assert "Atlantis FC" in r.json()["detail"]


@pytest.mark.asyncio
async def test_predict_endpoint_reports_unavailable_model(client):
    with patch("app.services.prediction_service.get_model_loader", side_effect=ModelUnavailable("checksum mismatch")):
        async with client as c:
            r = await c.post(PREDICT, json={"home_team": "France", "away_team": "Brazil"})
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()
    assert "probability" not in r.text


# ═══════════════════════════════════════════════════════════════════════════
# POST /tournament/simulate
# ═══════════════════════════════════════════════════════════════════════════

STAGE_KEYS = {"group", "r32", "r16", "qf", "sf", "third_place", "final", "winner"}


@pytest.mark.asyncio
async def test_simulate_pre_tournament_forecast(client):
    async with client as c:
        r = await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 2000, "use_real_results": False})
    assert r.status_code == 200
    d = r.json()
    probs, meta = d["probabilities"], d["meta"]
    assert set(probs) == set(wc2026.code_to_name())
    assert all(set(v) == STAGE_KEYS for v in probs.values())
    assert sum(v["winner"] for v in probs.values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(v["r32"] for v in probs.values()) == pytest.approx(32.0, abs=1e-9)
    assert meta["engine"] == "v3" and meta["mode"] == "pre_tournament"
    assert meta["information_cutoff"] == "2026-06-11" and meta["data_through"] < "2026-06-11"
    assert meta["fixed_matches"] == 0 and meta["tournament_status"] == "completed"
    assert meta["model_version"].startswith("v3.") and meta["n_simulations"] == 2000
    # The legacy simulator collapsed 1,128 matchups into three distinct predictions,
    # which made 47 teams interchangeable. Real strength differences must show.
    assert len({round(v["winner"], 6) for v in probs.values()}) > 20
    assert len({round(v["r32"], 3) for v in probs.values()}) > 30


@pytest.mark.asyncio
async def test_simulate_after_group_stage_uses_real_groups_only(client):
    async with client as c:
        r = await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 1000, "use_real_results": True})
    assert r.status_code == 200
    d = r.json()
    probs, meta = d["probabilities"], d["meta"]
    assert meta["mode"] == "after_group_stage" and meta["fixed_matches"] == 72
    assert meta["information_cutoff"] == "2026-06-28"
    reached = [v["r32"] for v in probs.values()]
    assert sorted(set(reached)) == [0.0, 1.0] and sum(reached) == 32.0     # the group stage is not re-simulated
    assert sum(v["winner"] for v in probs.values()) == pytest.approx(1.0, abs=1e-9)
    # No knockout result is given to it: no team's title is certain.
    assert max(v["winner"] for v in probs.values()) < 0.6


@pytest.mark.asyncio
async def test_simulate_is_reproducible_with_a_seed(client):
    body = {"use_fifa_2026_groups": True, "n_simulations": 500, "use_real_results": False}
    tournament_forecast._results.clear()
    async with client as c:
        a = (await c.post(SIMULATE, json={**body, "seed": 7})).json()
        tournament_forecast._results.clear()          # recompute rather than read the result cache
        b = (await c.post(SIMULATE, json={**body, "seed": 7})).json()
        other = (await c.post(SIMULATE, json={**body, "seed": 8})).json()
    assert a["probabilities"] == b["probabilities"]
    assert a["probabilities"] != other["probabilities"]
    assert a["meta"]["seed"] == 7


@pytest.mark.asyncio
async def test_simulate_custom_groups_of_real_teams(client):
    codes = sorted(wc2026.code_to_name())
    groups = [{"name": f"G{i + 1}", "teams": codes[i * 4:(i + 1) * 4]} for i in range(12)]
    async with client as c:
        r = await c.post(SIMULATE, json={"groups": groups, "n_simulations": 500})
    assert r.status_code == 200
    d = r.json()
    assert set(d["probabilities"]) == set(codes)                       # keyed by the caller's own labels
    assert sum(v["winner"] for v in d["probabilities"].values()) == pytest.approx(1.0, abs=1e-9)
    assert d["meta"]["mode"] == "custom_groups" and d["meta"]["tournament_status"] == "hypothetical"
    assert d["meta"]["group_letters"]["G1"] == "A" and d["meta"]["fixed_matches"] == 0


@pytest.mark.asyncio
async def test_simulate_refuses_teams_it_knows_nothing_about(client):
    groups = [{"name": "ABCDEFGHIJKL"[g], "teams": [f"Team{g}_{i}" for i in range(4)]} for g in range(12)]
    async with client as c:
        r = await c.post(SIMULATE, json={"groups": groups, "n_simulations": 100})
    assert r.status_code == 422
    assert "no match history" in r.json()["detail"]


@pytest.mark.asyncio
async def test_simulate_rejects_the_same_team_under_two_labels(client):
    codes = sorted(wc2026.code_to_name())
    groups = [{"name": "ABCDEFGHIJKL"[i], "teams": codes[i * 4:(i + 1) * 4]} for i in range(12)]
    groups[0]["teams"][0] = wc2026.code_to_name()[groups[1]["teams"][0]]   # a name duplicating a code
    async with client as c:
        r = await c.post(SIMULATE, json={"groups": groups, "n_simulations": 100})
    assert r.status_code == 422 and "same team" in r.json()["detail"]


@pytest.mark.asyncio
async def test_simulate_reports_unavailable_model_without_numbers(client):
    with patch("app.services.tournament_forecast.simulate_tournament", side_effect=ModelUnavailable("bad bundle")):
        async with client as c:
            r = await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 100})
    assert r.status_code == 503
    assert "probabilities" not in r.json()


@pytest.mark.asyncio
async def test_simulate_validation_still_applies(client):
    async with client as c:
        assert (await c.post(SIMULATE, json={"n_simulations": 100})).status_code == 422
        assert (await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 1})).status_code == 422
        assert (await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 10 ** 7})).status_code == 422


@pytest.mark.asyncio
async def test_simulate_is_still_rate_limited(v3_engine):
    """The V3 path must not bypass the limiter: it is checked before any work is done."""
    from fastapi import HTTPException
    limiter = AsyncMock(side_effect=HTTPException(status_code=429, detail="Rate limit exceeded"))
    with patch("app.api.v1.endpoints.tournament.check_rate_limit", limiter), \
         patch("app.services.tournament_forecast.simulate_tournament") as sim:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 100})
    assert r.status_code == 429
    limiter.assert_awaited_once()
    sim.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# Team identity: every way the application names a team reaches the same team
# ═══════════════════════════════════════════════════════════════════════════

def test_all_48_codes_display_names_and_form_names_resolve_to_48_teams():
    from app.data import wc2026 as app_wc2026
    from app.data.fifa_2026 import load_groups

    svc = get_service()
    official = {t["code"]: t["name"] for teams in load_groups().values() for t in teams}
    assert len(official) == 48
    by_code = {code: svc.resolve(code) for code in official}
    assert None not in by_code.values()
    assert len(set(by_code.values())) == 48
    # The display name the UI shows and the FIFA code are the same team.
    assert {code: svc.resolve(name) for code, name in official.items()} == by_code
    # So are the names the prediction form submits.
    form_names = list(app_wc2026.load_wc2026_teams())
    assert len(form_names) == 48
    assert {svc.resolve(n) for n in form_names} == set(by_code.values())
    assert by_code == {c: n for c, n in wc2026.code_to_name().items()}


def test_resolver_accepts_aliases_and_refuses_strangers():
    svc = get_service()
    assert svc.resolve("USA") == svc.resolve("usa") == svc.resolve("United States") == "USA"
    assert svc.resolve("Korea Republic") == svc.resolve("KOR") == "South Korea"
    assert svc.resolve("Bosnia & Herzegovina") == "Bosnia and Herzegovina"
    assert svc.resolve("Atlantis FC") is None
    assert svc.resolve("ZZZ") is None


@pytest.mark.asyncio
async def test_predict_endpoint_accepts_code_or_display_name(client):
    async with client as c:
        by_name = (await c.post(PREDICT, json={"home_team": "South Korea", "away_team": "Spain", "neutral_venue": True})).json()
        by_display = (await c.post(PREDICT, json={"home_team": "Korea Republic", "away_team": "ESP", "neutral_venue": True})).json()
    for key in ("home_win_probability", "draw_probability", "away_win_probability", "most_likely_score"):
        assert by_name[key] == by_display[key]
    assert by_display["home_team"] == "Korea Republic"          # the caller's own label is echoed back


@pytest.mark.asyncio
async def test_legacy_simulation_reports_itself_as_legacy(legacy_engine):
    """The default engine labels its output, so the UI never describes it as something else."""
    from unittest.mock import MagicMock
    import pandas as pd

    predictor = MagicMock()
    predictor.is_loaded = True
    predictor.model_version = "1.0.0"
    predictor.predict_batch = lambda df, pairs, **kw: [
        {"home_team": a, "away_team": b, "expected_home_goals": 1.2, "expected_away_goals": 1.0,
         "home_win_probability": 0.45, "draw_probability": 0.25, "away_win_probability": 0.30} for a, b in pairs]
    with patch("app.api.v1.endpoints.tournament.check_rate_limit", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.tournament._get_simulator_dependencies", new_callable=AsyncMock,
               return_value=(predictor, pd.DataFrame())):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120) as c:
            r = await c.post(SIMULATE, json={"use_fifa_2026_groups": True, "n_simulations": 100, "use_real_results": False})
    assert r.status_code == 200
    d = r.json()
    assert d["meta"]["engine"] == "legacy" and d["meta"]["mode"] == "legacy"
    assert set(d["probabilities"]) == set(wc2026.code_to_name())
    assert sum(v["winner"] for v in d["probabilities"].values()) == pytest.approx(1.0, abs=1e-6)
