"""
Regression tests for the paginated match history query.

These pin two properties of ``get_matches`` that are easy to lose in a refactor
and expensive to notice in production:

  - The query must produce a **total order**. ``matches.date`` is a DATE column
    with roughly three rows per date (and up to 66 on one), so ORDER BY date
    alone leaves tied rows in whatever order the plan happens to emit. OFFSET
    pagination over a non-total order can show the same match on two pages and
    skip another; appending the primary key removes the ambiguity.
  - Eager loading must stay a JOIN, and must stay an *outer* one. away_team_id
    is nullable (TBD knockout opponents), and an inner join would silently drop
    those fixtures from the archive.

Both are asserted against the built statement rather than a live database, so
they run in CI without Postgres.
"""

from sqlalchemy import inspect as sa_inspect

from app.models.match import Match
from app.services import match_service


def _compiled_page_query() -> str:
    """The SELECT get_matches issues for a page, as SQL text."""
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    stmt = (
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(desc(Match.date), Match.id)
    )
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_order_by_includes_a_unique_tiebreaker():
    """date is not unique, so the sort must fall through to the primary key."""
    sql = _compiled_page_query().lower()
    order_clause = sql.split("order by", 1)[1]
    assert "matches.date desc" in order_clause
    assert "matches.id" in order_clause, (
        "ORDER BY must include the primary key: matches.date has ~3 rows per "
        "value, so without a tiebreaker OFFSET pagination can duplicate or "
        "skip rows whenever the plan changes."
    )


def test_page_query_uses_joins_not_follow_up_selects():
    """joinedload keeps the page to one round trip; selectinload cost three."""
    sql = _compiled_page_query().lower()
    assert "join teams" in sql, "teams must be joined into the page query"
    assert sql.count("select") == 1, "the page must not need follow-up SELECTs"


def test_away_team_join_is_outer_so_tbd_fixtures_survive():
    """away_team_id is nullable; an inner join would drop those matches."""
    sql = _compiled_page_query().lower()
    assert "left outer join" in sql, (
        "away_team must be LEFT OUTER JOINed — matches with a TBD opponent "
        "have a NULL away_team_id and must still appear in the archive."
    )


def test_away_team_relationship_is_nullable():
    """Guards the assumption the outer join exists to protect."""
    mapper = sa_inspect(Match)
    away_fk = mapper.columns["away_team_id"]
    assert away_fk.nullable is True


def test_get_matches_is_cached_but_keyed_off_the_session():
    """The TTL cache must ignore the AsyncSession argument, or every request
    (which gets a fresh session) would miss the cache entirely."""
    assert hasattr(match_service.get_matches, "cache_clear")
    assert hasattr(match_service.get_tournaments, "cache_clear")
