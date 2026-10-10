"""
V3 pipeline: data contract, chronological rating engine, feature registry,
models, calibration and the backtest splits.

The leakage tests are the important ones. They do not check that a column is
absent by name; they change a result and assert that nothing dated at or before
it moves.
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pandas as pd
import pytest

from app.ml.v3 import backtest, data, features, models, pipeline, ratings, tournament_fast
from app.ml.v3.calibration import CALIBRATORS, Temperature
from app.ml.v3.features import (ANTISYMMETRIC, FEATURE_NAMES, FORBIDDEN_INPUTS, feature_matrix, finalise, mirror)
from app.ml.v3.inference import get_service
from app.ml.v3.ratings import EloConfig, RatingEngine, elo_expected, margin_multiplier, walk
from app.ml.v3 import wc2026


@pytest.fixture(scope="module")
def matches() -> pd.DataFrame:
    return data.load_matches()


@pytest.fixture(scope="module")
def recent(matches) -> pd.DataFrame:
    """A few thousand consecutive real matches: enough to exercise every code path quickly."""
    return matches[matches["date"] >= "2019-01-01"].head(3000).reset_index(drop=True)


@pytest.fixture(scope="module")
def pre() -> "object":
    return get_service("wc2026_pretournament")


# ═══════════════════════════════════════════════════════════════════════════
# Data contract
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_columns_and_types(matches):
    required = {"match_id", "date", "team_a", "team_b", "goals_a", "goals_b", "result", "shootout_winner",
                "tournament", "tier", "importance", "venue", "venue_country", "source", "source_row"}
    assert required <= set(matches.columns)
    assert matches["match_id"].is_unique
    assert matches["date"].is_monotonic_increasing
    assert matches[["date", "team_a", "team_b", "goals_a", "goals_b", "tournament"]].notna().all().all()
    assert (matches["goals_a"] >= 0).all() and (matches["goals_b"] >= 0).all()
    assert (matches["team_a"] != matches["team_b"]).all()
    assert set(matches["venue"].unique()) <= {0, 1}
    assert set(matches["tier"].unique()) <= {1, 2, 3, 4, 5}
    assert (matches["importance"] == matches["tier"].map(data.TIER_WEIGHT)).all()


def test_result_label_agrees_with_score(matches):
    expected = np.where(matches.goals_a > matches.goals_b, "A", np.where(matches.goals_a < matches.goals_b, "B", "D"))
    assert (matches["result"].to_numpy() == expected).all()


def test_shootout_winner_is_one_of_the_two_teams(matches):
    so = matches[matches["shootout_winner"].notna()]
    assert len(so) > 400
    assert ((so["shootout_winner"] == so["team_a"]) | (so["shootout_winner"] == so["team_b"])).all()


def test_team_aliases_resolve_to_registry_names(matches):
    teams = set(matches["team_a"]) | set(matches["team_b"])
    for dataset_name, registry_name in data.DATASET_TO_REGISTRY.items():
        assert dataset_name not in teams, f"{dataset_name} should have been renamed"
        assert registry_name in teams


def test_every_world_cup_team_has_match_history(pre):
    """
    The root cause of the 'USA wins the World Cup' forecast: the simulator
    passed FIFA codes to a model keyed by names, so 47 of 48 teams had no
    history. Every code must map to a name the corpus actually knows.
    """
    mapping = wc2026.code_to_name()
    assert len(mapping) == 48
    unknown = [f"{code}->{name}" for code, name in mapping.items() if not pre.known(name)]
    assert unknown == []
    assert all(pre.engine.n[name] >= 50 for name in mapping.values())


def test_competition_tiers():
    assert data.competition_tier("FIFA World Cup") == 5
    assert data.competition_tier("UEFA Euro") == 4
    assert data.competition_tier("FIFA World Cup qualification") == 3
    assert data.competition_tier("Friendly") == 1


def test_loader_drops_invalid_rows_and_reports_them(tmp_path):
    csv = tmp_path / "results.csv"
    csv.write_text(
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2020-01-01,Aland,Borduria,2,1,Friendly,X,Aland,FALSE\n"
        "not-a-date,Aland,Borduria,1,1,Friendly,X,Aland,FALSE\n"
        "2020-01-03,Aland,Borduria,-1,0,Friendly,X,Aland,FALSE\n"
        "2020-01-04,Aland,Borduria,,0,Friendly,X,Aland,FALSE\n"
        "2020-01-05,Aland,Aland,1,0,Friendly,X,Aland,FALSE\n"
        "2020-01-06,United States,Borduria,0,0,Friendly,X,Syldavia,TRUE\n",
        encoding="utf-8",
    )
    out, rep = data.load_matches(csv, tmp_path / "no_shootouts.csv", return_report=True)
    assert len(out) == 2
    assert list(out["team_a"]) == ["Aland", "USA"]
    assert list(out["venue"]) == [1, 0]
    counts = rep.to_dict()
    flat = str(counts)
    assert "invalid_date_dropped" in flat and "missing_or_negative_score_dropped" in flat
    assert rep.rows_in == 6 and rep.rows_out == 2


def test_world_cup_2026_is_complete_in_the_corpus(matches):
    w = wc2026.wc2026_matches(matches)
    assert len(w) == 104
    assert w["date"].min() == wc2026.FORECAST_CUTOFF
    assert w["date"].max() == wc2026.TOURNAMENT_END


# ═══════════════════════════════════════════════════════════════════════════
# Elo and the rating engine
# ═══════════════════════════════════════════════════════════════════════════

def test_elo_update_matches_hand_calculation():
    eng = RatingEngine(EloConfig())
    day = pd.Timestamp("2020-01-01")
    eng.advance("A", "B", 2, 0, day, venue=1, importance=40.0)
    # Expected score for A at home with equal ratings: 1 / (1 + 10^(-100/400)).
    we = 1.0 / (1.0 + 10.0 ** (-100.0 / 400.0))
    assert we == pytest.approx(0.640065, abs=1e-6)
    # K = 40 (importance) x 1.5 (two-goal margin) x 1.5 (provisional: first 30 matches).
    delta = 40.0 * 1.5 * 1.5 * (1.0 - we)
    assert eng.elo["A"] == pytest.approx(1500.0 + delta, abs=1e-9)
    assert eng.elo["B"] == pytest.approx(1500.0 - delta, abs=1e-9)
    assert delta == pytest.approx(32.394, abs=1e-3)


def test_elo_is_zero_sum_between_established_teams():
    eng = RatingEngine(EloConfig(provisional_matches=0))
    day = pd.Timestamp("2020-01-01")
    eng.advance("A", "B", 1, 1, day, venue=0, importance=60.0)
    assert eng.elo["A"] == pytest.approx(1500.0) and eng.elo["B"] == pytest.approx(1500.0)
    eng.advance("A", "B", 3, 0, day, venue=0, importance=60.0)
    assert eng.elo["A"] + eng.elo["B"] == pytest.approx(3000.0)
    assert eng.elo["A"] > 1500.0


def test_elo_helpers():
    assert elo_expected(0.0) == 0.5
    assert elo_expected(400.0) == pytest.approx(10.0 / 11.0)
    assert [margin_multiplier(g) for g in (0, 1, -1, 2, 3, -4)] == [1.0, 1.0, 1.0, 1.5, 14 / 8, 15 / 8]


def test_snapshot_is_a_pure_read(recent):
    eng, _ = walk(recent, collect=False)
    a, b = recent.team_a.iloc[-1], recent.team_b.iloc[-1]
    day = pd.Timestamp("2030-01-01")
    before = (dict(eng.elo), dict(eng.n), dict(eng.attack), dict(eng.defence), eng.mu, eng.home, eng.matches_seen)
    s1 = eng.snapshot(a, b, day, 0, 5)
    s2 = eng.snapshot(a, b, day, 0, 5)
    after = (dict(eng.elo), dict(eng.n), dict(eng.attack), dict(eng.defence), eng.mu, eng.home, eng.matches_seen)
    assert s1 == s2
    assert before == after


def test_snapshot_mirrors_exactly_when_teams_are_swapped(recent):
    eng, _ = walk(recent, collect=False)
    day = pd.Timestamp("2030-01-01")
    teams = list(dict.fromkeys(recent.team_a))[:12]
    for a, b in zip(teams[::2], teams[1::2]):
        for venue in (1, 0, -1):
            x = finalise(pd.DataFrame([eng.snapshot(a, b, day, venue, 5)]))
            y = finalise(pd.DataFrame([eng.snapshot(b, a, day, -venue, 5)]))
            for f in FEATURE_NAMES:
                sign = -1.0 if f in ANTISYMMETRIC else 1.0
                assert x[f].iloc[0] == pytest.approx(sign * y[f].iloc[0], abs=1e-12), f


def test_walk_requires_chronological_order(recent):
    with pytest.raises(ValueError):
        walk(recent.iloc[::-1], collect=False)


# ═══════════════════════════════════════════════════════════════════════════
# Leakage
# ═══════════════════════════════════════════════════════════════════════════

def test_a_result_cannot_influence_its_own_or_earlier_features(recent):
    """Rewrite one match's score: every feature row up to and including that match is unchanged."""
    _, base = walk(recent)
    k = 1500
    tampered = recent.copy()
    tampered.loc[k, "goals_a"] = int(recent.loc[k, "goals_a"]) + 7
    _, changed = walk(tampered)
    pd.testing.assert_frame_equal(base.iloc[: k + 1], changed.iloc[: k + 1])
    # ...and the change does reach later matches, so the test is not vacuous.
    assert not base.iloc[k + 1:].equals(changed.iloc[k + 1:])


def test_future_matches_cannot_influence_earlier_features(recent):
    """Features for the first N matches are identical whether or not later matches exist."""
    _, short = walk(recent.iloc[:1000])
    _, full = walk(recent)
    pd.testing.assert_frame_equal(short, full.iloc[:1000])


def test_registry_is_what_the_engine_produces_and_nothing_forbidden(recent):
    _, snap = walk(recent.iloc[:50])
    frame = finalise(snap)
    assert set(FEATURE_NAMES) <= set(frame.columns)
    assert not FORBIDDEN_INPUTS & set(FEATURE_NAMES)
    assert list(feature_matrix(frame).columns) == list(FEATURE_NAMES)
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES)) == 14
    with pytest.raises(KeyError):
        feature_matrix(frame.drop(columns=["elo_diff"]))


def test_model_matrix_ignores_result_columns(pre):
    """Outcome columns sitting in the frame change nothing: the matrix is selected by registry name."""
    frame = pre._frame([("Spain", "Brazil", 0), ("Japan", "Mexico", 0)], 5)
    p0 = pre.forecaster.predict_proba(frame)
    poisoned = frame.assign(goals_a=9, goals_b=0, result="A", shootout_winner="Spain")
    assert np.array_equal(p0, pre.forecaster.predict_proba(poisoned))


def test_pretournament_bundle_never_saw_the_tournament(pre):
    meta = pre.forecaster.meta
    assert pre.manifest["information_cutoff"] == "2026-06-11"
    assert pd.Timestamp(meta["train_last_match"]) < wc2026.FORECAST_CUTOFF
    assert pd.Timestamp(meta["calibration_window"][1]) <= wc2026.FORECAST_CUTOFF
    assert pre.engine.last_match_date < wc2026.FORECAST_CUTOFF
    assert pd.Timestamp(pre.data_through) < wc2026.FORECAST_CUTOFF


def test_team_state_cannot_be_moved_before_the_training_cutoff(pre):
    with pytest.raises(ValueError):
        pre.advanced_to(pd.Timestamp("2026-01-01"), "x")


def test_backtest_folds_are_chronological_and_disjoint(matches):
    frame = matches[matches["date"] >= "2000-01-01"]
    previous_test_end = None
    for fold in backtest.FOLDS:
        train, val, test = backtest.split(frame, fold)
        assert train["date"].max() < val["date"].min()
        assert val["date"].max() < test["date"].min()
        assert not set(train.match_id) & set(test.match_id)
        assert not set(val.match_id) & set(test.match_id)
        if previous_test_end is not None:
            assert pd.Timestamp(fold.test_start) >= previous_test_end
        previous_test_end = pd.Timestamp(fold.test_end)
    assert backtest.FINAL_FOLD.final and not any(f.final for f in backtest.DEV_FOLDS)


# ═══════════════════════════════════════════════════════════════════════════
# Score model
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("lam_a,lam_b,rho", [(1.3, 1.1, 0.0), (0.4, 2.6, -0.06), (2.2, 0.3, -0.12), (1.0, 1.0, 0.05)])
def test_score_matrix_is_a_probability_distribution(lam_a, lam_b, rho):
    m = models.score_matrix(lam_a, lam_b, rho)
    assert m.shape == (models.MAX_GOALS + 1, models.MAX_GOALS + 1)
    assert (m >= 0).all()
    assert m.sum() == pytest.approx(1.0, abs=1e-12)
    assert sum(models.outcome_from_matrix(m)) == pytest.approx(1.0, abs=1e-12)
    goals = np.arange(models.MAX_GOALS + 1)
    assert (m.sum(axis=1) * goals).sum() == pytest.approx(lam_a, abs=0.02)
    assert (m.sum(axis=0) * goals).sum() == pytest.approx(lam_b, abs=0.02)


def test_dixon_coles_correction_moves_only_the_low_scores():
    plain = models.score_matrix(1.2, 1.0, 0.0)
    dc = models.score_matrix(1.2, 1.0, -0.08)
    ratio = dc / plain
    changed = np.abs(ratio - ratio[5, 5]) > 1e-9
    assert set(zip(*np.nonzero(changed))) == {(0, 0), (0, 1), (1, 0), (1, 1)}
    # Negative rho raises 0-0 and 1-1 relative to independence, lowers 1-0 and 0-1.
    assert ratio[0, 0] > ratio[5, 5] and ratio[1, 1] > ratio[5, 5]
    assert ratio[1, 0] < ratio[5, 5] and ratio[0, 1] < ratio[5, 5]


def test_equal_teams_give_symmetric_matrix():
    m = models.score_matrix(1.25, 1.25, -0.05)
    assert np.allclose(m, m.T)
    a, d, b = models.outcome_from_matrix(m)
    assert a == pytest.approx(b)


# ═══════════════════════════════════════════════════════════════════════════
# Forecaster
# ═══════════════════════════════════════════════════════════════════════════

def _sample_fixtures(pre, n=60, seed=0):
    rng = np.random.default_rng(seed)
    teams = sorted(wc2026.code_to_name().values())
    out = []
    while len(out) < n:
        a, b = rng.choice(teams, 2, replace=False)
        out.append((str(a), str(b), int(rng.choice([-1, 0, 1]))))
    return out


def test_probabilities_are_valid(pre):
    frame = pre._frame(_sample_fixtures(pre), 5)
    p = pre.forecaster.predict_proba(frame)
    assert p.shape == (len(frame), 3)
    assert np.isfinite(p).all() and (p > 0).all() and (p < 1).all()
    assert np.allclose(p.sum(axis=1), 1.0, atol=1e-12)
    la, lb = pre.forecaster.predict_goals(frame)
    assert (la > 0).all() and (lb > 0).all() and (la < 8).all() and (lb < 8).all()


def test_prediction_does_not_depend_on_team_order(pre):
    """P(A beats B) listed as A v B equals P(A beats B) listed as B v A, at every venue."""
    fixtures = _sample_fixtures(pre)
    p = pre.forecaster.predict_proba(pre._frame(fixtures, 5))
    q = pre.forecaster.predict_proba(pre._frame([(b, a, -v) for a, b, v in fixtures], 5))
    # Symmetric by construction; what is left is float32 rounding inside the tree model.
    assert np.abs(p - q[:, ::-1]).max() < 1e-7


def test_scoreline_matrix_carries_exactly_the_outcome_probabilities(pre):
    frame = pre._frame(_sample_fixtures(pre, 20), 5)
    mats, p, la, lb = pre.forecaster.score_matrices(frame)
    n = models.MAX_GOALS + 1
    for k in range(len(frame)):
        m = mats[k]
        assert m.sum() == pytest.approx(1.0, abs=1e-12) and (m >= 0).all()
        assert np.tril(m, -1).sum() == pytest.approx(p[k, 0], abs=1e-9)
        assert np.trace(m) == pytest.approx(p[k, 1], abs=1e-9)
        assert np.triu(m, 1).sum() == pytest.approx(p[k, 2], abs=1e-9)
    assert mats.shape == (len(frame), n, n)


def test_home_advantage_is_monotonic_and_applies_to_every_team(pre):
    """Venue helps whoever is at home; it is a fixture property, not a property of particular teams."""
    for a, b in [("USA", "Spain"), ("Japan", "Brazil"), ("Senegal", "England"), ("Uzbekistan", "Mexico")]:
        home = pre.predict(a, b, venue=1)["team_a_win_probability"]
        neutral = pre.predict(a, b, venue=0)["team_a_win_probability"]
        away = pre.predict(a, b, venue=-1)["team_a_win_probability"]
        assert home > neutral > away, (a, b)


def test_stronger_rated_side_is_favoured_at_a_neutral_venue(pre):
    elo = pre.engine.elo
    names = sorted(wc2026.code_to_name().values(), key=lambda t: -elo[t])
    strongest, weakest = names[0], names[-1]
    out = pre.predict(strongest, weakest, venue=0)
    assert out["team_a_win_probability"] > 0.6 > out["team_b_win_probability"]


def test_shootout_probability_is_symmetric_and_bounded(pre):
    f = pre.forecaster
    assert f.p_shootout(0.0) == pytest.approx(0.5)
    d = np.array([-400.0, -100.0, 100.0, 400.0])
    p = f.p_shootout(d)
    assert np.allclose(p + p[::-1], 1.0)
    assert 0.25 < p.min() and p.max() < 0.75      # an edge, not a certainty


def test_no_team_is_named_in_the_modelling_code():
    """Nothing in the model, the features or the simulator may special-case a country."""
    names = [n for n in wc2026.code_to_name().values() if len(n) > 3] + ["USA"]
    for module in (ratings, features, models, pipeline, tournament_fast, backtest):
        source = inspect.getsource(module)
        hits = [n for n in names if f'"{n}"' in source or f"'{n}'" in source]
        assert hits == [], f"{module.__name__} mentions {hits}"


# ═══════════════════════════════════════════════════════════════════════════
# Calibration and metrics
# ═══════════════════════════════════════════════════════════════════════════

def _toy_probs(n=4000, seed=1):
    rng = np.random.default_rng(seed)
    true = rng.dirichlet([2.0, 1.2, 1.6], size=n)
    y = np.array([rng.choice(3, p=row) for row in true])
    return true, y


@pytest.mark.parametrize("name", sorted(CALIBRATORS))
def test_calibrators_return_valid_probabilities(name):
    p, y = _toy_probs()
    q = CALIBRATORS[name]().fit(p[:2000], y[:2000]).transform(p[2000:])
    assert q.shape == (2000, 3)
    assert np.isfinite(q).all() and (q >= 0).all()
    assert np.allclose(q.sum(axis=1), 1.0, atol=1e-9)


def test_temperature_cools_overconfident_probabilities():
    p, y = _toy_probs()
    sharp = p ** 3
    sharp /= sharp.sum(axis=1, keepdims=True)
    cal = Temperature().fit(sharp, y)
    assert cal.T > 1.5
    assert backtest.log_loss(cal.transform(sharp), y) < backtest.log_loss(sharp, y)
    assert Temperature().fit(p, y).T == pytest.approx(1.0, abs=0.1)


def test_metrics_on_known_cases():
    y = np.array([0, 1, 2, 0])
    uniform = np.full((4, 3), 1 / 3)
    assert backtest.log_loss(uniform, y) == pytest.approx(math.log(3))
    perfect = np.eye(3)[y]
    assert backtest.rps(perfect, y) == pytest.approx(0.0, abs=1e-9)
    assert backtest.brier(perfect, y) == pytest.approx(0.0, abs=1e-9)
    # RPS respects order: predicting a draw when A won is less wrong than predicting B.
    a_won = np.array([0])
    assert backtest.rps(np.array([[0.0, 1.0, 0.0]]), a_won) < backtest.rps(np.array([[0.0, 0.0, 1.0]]), a_won)


def test_blend_is_a_convex_combination():
    p, _ = _toy_probs(50)
    q = p[:, ::-1].copy()
    b = models.blend([p, q], np.array([0.5, 0.5]))
    assert np.allclose(b.sum(axis=1), 1.0)
    assert np.allclose(b, models.normalise(0.5 * p + 0.5 * q), atol=1e-9)
