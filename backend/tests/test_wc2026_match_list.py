"""The World Cup 2026 match list is served from the canonical dataset, and goal timing is gone."""
import asyncio
from datetime import date

from app.main import app
from app.services import match_service as ms


class _Result:
    def scalars(self):
        return self

    def all(self):
        return []


class _FakeDb:
    async def execute(self, _stmt):
        return _Result()


def _all():
    return asyncio.run(ms._get_wc2026_matches(_FakeDb(), 1, 200, None, None, None))


def test_filter_detection():
    assert ms._wants_wc2026("FIFA World Cup 2026", None)
    assert ms._wants_wc2026("fifa world cup 2026", 2026)
    assert not ms._wants_wc2026("FIFA World Cup 2022", None)
    assert not ms._wants_wc2026("FIFA World Cup 2026", 2022)
    assert not ms._wants_wc2026(None, None)


def test_all_104_fixtures_with_real_results_and_known_opponents():
    out = _all()
    assert out.total == 104 and len(out.data) == 104
    assert all(m.status == "completed" and m.home_score is not None and m.away_score is not None for m in out.data)
    assert all(m.away_team is not None for m in out.data)


def test_final_uses_the_extra_time_score_and_is_newest_first():
    out = _all()
    final = out.data[0]
    assert (final.stage, final.home_team["name"], final.away_team["name"]) == ("final", "Spain", "Argentina")
    assert (final.home_score, final.away_score, final.result_method) == (1, 0, "Extra Time")
    dates = [m.date for m in out.data]
    assert dates == sorted(dates, reverse=True)


def test_shootouts_stay_level_and_carry_the_penalties():
    pens = [m for m in _all().data if m.result_method == "Penalties"]
    assert pens
    for m in pens:
        assert m.home_score == m.away_score
        assert m.home_penalties is not None and m.away_penalties is not None and m.home_penalties != m.away_penalties


def test_team_and_date_filters_and_pagination():
    england = asyncio.run(ms._get_wc2026_matches(_FakeDb(), 1, 50, "england", None, None))
    assert england.total >= 3 and all("England" in (m.home_team["name"], m.away_team["name"]) for m in england.data)
    late = asyncio.run(ms._get_wc2026_matches(_FakeDb(), 1, 50, None, date(2026, 7, 18), None))
    assert late.total == 2
    page2 = asyncio.run(ms._get_wc2026_matches(_FakeDb(), 2, 20, None, None, None))
    assert len(page2.data) == 20 and page2.total_pages == 6


def test_goal_timing_endpoint_is_removed():
    paths = app.openapi()["paths"]
    assert "/api/v1/matches/analytics/goal-distribution" not in paths
    assert "/api/v1/matches/analytics/scorelines" in paths
    assert not hasattr(ms, "get_goal_distribution")


def test_overview_total_uses_the_same_count_as_the_match_list():
    class _Scalar:
        def scalar(self):
            return 49_228

    class _CountDb:
        async def execute(self, _stmt):
            return _Scalar()

    total = asyncio.run(ms.count_all_matches(_CountDb()))
    assert total == 49_228 + len(ms._canonical_wc2026_rows()) == 49_332
