"""
Guards on the two caches added to the hottest read paths.

Both exist because this deployment pays a cross-region round trip (~150ms) for
every database call while the queries themselves run in single-digit
milliseconds, so the win is in not making the call at all.

The dangerous failure mode for a shared cache is leaking one caller's data to
another. ``_global_dashboard_block`` is keyed on nothing (max_size=1, the
session argument ignored), so **every** visitor shares one entry. These tests
pin the property that makes that safe: the cached function reads only
caller-independent data, and the per-user half of the dashboard is computed
outside it.
"""

import ast
import inspect
import textwrap

from app.api.v1.endpoints import analytics
from app.services import team_service


def _code_without_docstring(fn) -> str:
    """AST dump of a function body with the docstring removed.

    The docstrings here talk *about* users, so a plain substring scan over the
    source would false-positive on its own prose.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return "\n".join(ast.dump(node) for node in body)


def test_shared_dashboard_cache_reads_nothing_user_scoped():
    code = _code_without_docstring(analytics._global_dashboard_block.__wrapped__)
    for forbidden in ("SavedPrediction", "get_recent_predictions", "user_id"):
        assert forbidden not in code, (
            f"{forbidden!r} appears inside _global_dashboard_block, which is a "
            "process-wide cache shared by every caller — per-user data must be "
            "read in dashboard_stats instead."
        )


def test_shared_dashboard_cache_takes_only_a_session():
    """No parameter that could carry a caller identity into the cache key."""
    params = list(inspect.signature(analytics._global_dashboard_block.__wrapped__).parameters)
    assert params == ["db"], params


def test_dashboard_endpoint_still_computes_per_user_stats_itself():
    """The user half must stay outside the shared cache."""
    code = _code_without_docstring(analytics.dashboard_stats)
    assert "SavedPrediction" in code
    assert "get_recent_predictions" in code


def test_hot_reference_reads_are_cached():
    """These are the reads that were costing a round trip on every request."""
    for fn in (
        analytics._global_dashboard_block,
        team_service.get_wc2026_teams,
        team_service.get_top_teams,
    ):
        assert hasattr(fn, "cache_clear"), f"{fn.__name__} should be TTL-cached"


def test_wc2026_roster_cache_ignores_the_session_argument():
    """A fresh AsyncSession per request must still hit the cache."""
    closure = team_service.get_wc2026_teams.__closure__ or ()
    assert closure, "expected the decorator's closure"
    # ignore_args={0} is what makes the session argument non-keying.
    assert any(getattr(c.cell_contents, "__contains__", None) and 0 in c.cell_contents
               for c in closure if isinstance(c.cell_contents, (set, frozenset)))
