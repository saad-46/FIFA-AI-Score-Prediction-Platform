import pytest
from itertools import combinations
from unittest.mock import MagicMock
import pandas as pd
from app.ml.tournament_simulator import TournamentSimulator

@pytest.fixture
def mock_simulator():
    predictor = MagicMock()
    # Mock prediction dictionary
    def mock_predict(*args, **kwargs):
        class MockPred:
            home_team = kwargs.get('home_team', 'A')
            away_team = kwargs.get('away_team', 'B')
            expected_home_goals = 1.0
            expected_away_goals = 1.0
            home_win_probability = 0.4
            away_win_probability = 0.4
            draw_probability = 0.2
        return MockPred()
        
    predictor.predict = mock_predict
    df = pd.DataFrame()
    return TournamentSimulator(predictor=predictor, df=df)

def test_tournament_simulator_initialization(mock_simulator):
    assert mock_simulator is not None
    assert hasattr(mock_simulator, 'simulate_tournament')

def test_tournament_simulator_48_teams(mock_simulator):
    groups = {
        "A": ["A1", "A2", "A3", "A4"],
        "B": ["B1", "B2", "B3", "B4"],
        "C": ["C1", "C2", "C3", "C4"],
        "D": ["D1", "D2", "D3", "D4"],
        "E": ["E1", "E2", "E3", "E4"],
        "F": ["F1", "F2", "F3", "F4"],
        "G": ["G1", "G2", "G3", "G4"],
        "H": ["H1", "H2", "H3", "H4"],
        "I": ["I1", "I2", "I3", "I4"],
        "J": ["J1", "J2", "J3", "J4"],
        "K": ["K1", "K2", "K3", "K4"],
        "L": ["L1", "L2", "L3", "L4"],
    }

    # Run a small simulation
    results = mock_simulator.simulate_tournament(groups, n_simulations=10)

    assert len(results) == 48
    assert "A1" in results

    stats = results["A1"]
    assert "group" in stats
    assert "r32" in stats
    assert "r16" in stats
    assert "qf" in stats
    assert "sf" in stats
    assert "third_place" in stats
    assert "final" in stats
    assert "winner" in stats


# ─── Regression: _run_simulation_batch KeyError-in-subprocess bug ───────────
#
# Previously, _run_simulation_batch crashed on every batch inside the
# ProcessPoolExecutor with a KeyError that was silently swallowed by the
# executor plumbing, so simulate_tournament always fell back to a result
# where every team had group=1.0 and every other stage (r32, r16, qf, sf,
# third_place, final, winner) was 0.0 for *all* 48 teams — i.e. the
# probabilities never summed to anything meaningful and "winner" never added
# up to 1.0 across the field. These tests pin down the fixed behaviour so a
# regression of that bug (e.g. re-introducing a KeyError in
# _run_simulation_batch, or a future change that silently drops batch
# failures) gets caught immediately.

def test_tournament_simulator_winner_probabilities_sum_to_one(mock_simulator):
    """The 'winner' stage probability, summed across all 48 teams, must be
    ~1.0 (exactly one team wins each simulated tournament) — not 0.0 for
    everyone, which was the silent failure mode of the batch-crash bug."""
    groups = {
        "A": ["A1", "A2", "A3", "A4"],
        "B": ["B1", "B2", "B3", "B4"],
        "C": ["C1", "C2", "C3", "C4"],
        "D": ["D1", "D2", "D3", "D4"],
        "E": ["E1", "E2", "E3", "E4"],
        "F": ["F1", "F2", "F3", "F4"],
        "G": ["G1", "G2", "G3", "G4"],
        "H": ["H1", "H2", "H3", "H4"],
        "I": ["I1", "I2", "I3", "I4"],
        "J": ["J1", "J2", "J3", "J4"],
        "K": ["K1", "K2", "K3", "K4"],
        "L": ["L1", "L2", "L3", "L4"],
    }

    results = mock_simulator.simulate_tournament(groups, n_simulations=64)

    winner_total = sum(stats["winner"] for stats in results.values())
    assert winner_total == pytest.approx(1.0, abs=1e-6)

    final_total = sum(stats["final"] for stats in results.values())
    assert final_total == pytest.approx(2.0, abs=1e-6)  # 2 finalists every sim

    # The exact bug: everything except "group" silently stuck at 0.0 for
    # every single team. Assert that is NOT the case — at least some teams
    # must have a nonzero probability of reaching each knockout stage.
    assert any(stats["r32"] > 0 for stats in results.values())
    assert any(stats["r16"] > 0 for stats in results.values())
    assert any(stats["qf"] > 0 for stats in results.values())
    assert any(stats["sf"] > 0 for stats in results.values())
    assert any(stats["final"] > 0 for stats in results.values())
    assert any(stats["winner"] > 0 for stats in results.values())


def test_tournament_simulator_group_probability_always_one(mock_simulator):
    """Every team plays the group stage in every simulation, so 'group'
    should always normalize to exactly 1.0 regardless of n_simulations."""
    groups = {
        "A": ["A1", "A2", "A3", "A4"],
        "B": ["B1", "B2", "B3", "B4"],
        "C": ["C1", "C2", "C3", "C4"],
        "D": ["D1", "D2", "D3", "D4"],
        "E": ["E1", "E2", "E3", "E4"],
        "F": ["F1", "F2", "F3", "F4"],
        "G": ["G1", "G2", "G3", "G4"],
        "H": ["H1", "H2", "H3", "H4"],
        "I": ["I1", "I2", "I3", "I4"],
        "J": ["J1", "J2", "J3", "J4"],
        "K": ["K1", "K2", "K3", "K4"],
        "L": ["L1", "L2", "L3", "L4"],
    }

    results = mock_simulator.simulate_tournament(groups, n_simulations=32)

    for team, stats in results.items():
        assert stats["group"] == 1.0, f"{team} group probability should be 1.0"


def test_run_simulation_batch_does_not_raise_and_produces_nonzero_stats():
    """Directly exercise the previously-buggy worker function
    (_run_simulation_batch) to prove it can run a batch to completion without
    raising, and that it produces nonzero counts for knockout stages — this
    is what silently failed (via a swallowed KeyError) inside the
    ProcessPoolExecutor before the fix."""
    from app.ml.tournament_simulator import _run_simulation_batch

    groups = {
        "A": ["A1", "A2", "A3", "A4"],
        "B": ["B1", "B2", "B3", "B4"],
        "C": ["C1", "C2", "C3", "C4"],
        "D": ["D1", "D2", "D3", "D4"],
        "E": ["E1", "E2", "E3", "E4"],
        "F": ["F1", "F2", "F3", "F4"],
        "G": ["G1", "G2", "G3", "G4"],
        "H": ["H1", "H2", "H3", "H4"],
        "I": ["I1", "I2", "I3", "I4"],
        "J": ["J1", "J2", "J3", "J4"],
        "K": ["K1", "K2", "K3", "K4"],
        "L": ["L1", "L2", "L3", "L4"],
    }
    all_teams = [t for g in groups.values() for t in g]

    matchup_cache = {}
    for t1, t2 in combinations(all_teams, 2):
        key = "|".join(sorted([t1, t2]))
        matchup_cache[key] = {
            "home_team": t1,
            "away_team": t2,
            "expected_home_goals": 1.2,
            "expected_away_goals": 1.0,
            "home_win_probability": 0.45,
            "away_win_probability": 0.30,
            "draw_probability": 0.25,
        }

    batch_stats = _run_simulation_batch(groups, matchup_cache, batch_size=20)

    assert len(batch_stats) == 48
    winner_total = sum(s["winner"] for s in batch_stats.values())
    assert winner_total == 20  # exactly one winner per simulated tournament
    assert sum(s["r32"] for s in batch_stats.values()) > 0
    assert sum(s["final"] for s in batch_stats.values()) == 40  # 2 finalists x 20 sims
