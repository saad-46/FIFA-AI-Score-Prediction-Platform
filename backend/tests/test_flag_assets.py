"""
Validates the bundled WC2026 flag assets against the canonical team registry.

This test deliberately reaches across into the frontend's `public/flags`
directory. The two are a single contract — `TeamFlag` resolves a team's FIFA
code straight to `/flags/{code}.svg` — and nothing else in CI would notice a
team gaining a flag, losing one, or being renamed. Rendering the wrong
country's flag is a worse failure than rendering none, so the mapping is
checked rather than trusted.

Skips (rather than fails) when the frontend tree is absent, so backend-only
checkouts and containers still run green.
"""

from pathlib import Path

import pytest

from app.data.wc2026 import load_wc2026_teams

_FLAGS_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "flags"

pytestmark = pytest.mark.skipif(
    not _FLAGS_DIR.exists(),
    reason="frontend/public/flags not present in this checkout",
)


def _bundled_codes() -> set[str]:
    return {p.stem.lower() for p in _FLAGS_DIR.glob("*.svg")}


def test_every_wc2026_team_has_a_bundled_flag():
    teams = load_wc2026_teams()
    bundled = _bundled_codes()
    missing = sorted(
        f"{name} ({meta['fifa_code']})"
        for name, meta in teams.items()
        if (meta["fifa_code"] or "").lower() not in bundled
    )
    assert not missing, f"teams with no flag asset: {missing}"


def test_flag_count_matches_the_48_team_field_exactly():
    """No extras either — a stray flag means a team was removed from the field
    without its asset being cleaned up, or a code was mistyped."""
    teams = load_wc2026_teams()
    expected = {(meta["fifa_code"] or "").lower() for meta in teams.values()}
    bundled = _bundled_codes()

    assert len(expected) == 48
    assert bundled == expected, (
        f"unexpected: {sorted(bundled - expected)}; missing: {sorted(expected - bundled)}"
    )


def test_flag_codes_are_unique_and_well_formed():
    teams = load_wc2026_teams()
    codes = [(meta["fifa_code"] or "") for meta in teams.values()]
    assert len(codes) == len(set(codes)), "duplicate FIFA codes in the WC2026 field"
    for code in codes:
        assert len(code) == 3 and code.isalpha() and code.isupper(), f"malformed code {code!r}"


def test_flag_assets_are_non_empty_svgs():
    """Guards against a truncated or placeholder copy — a 0-byte file would
    render as a broken image rather than hitting TeamFlag's fallback."""
    for path in _FLAGS_DIR.glob("*.svg"):
        content = path.read_text(encoding="utf-8", errors="ignore").lstrip()
        assert path.stat().st_size > 100, f"{path.name} is suspiciously small"
        assert content.startswith("<svg") or content.startswith("<?xml"), (
            f"{path.name} does not look like an SVG"
        )


def test_distinct_teams_do_not_share_a_flag_asset():
    """Catches the classic mis-mapping (e.g. KSA->Kosovo instead of Saudi
    Arabia) where two teams silently resolve to the same file."""
    contents: dict[str, str] = {}
    for path in sorted(_FLAGS_DIR.glob("*.svg")):
        body = path.read_text(encoding="utf-8", errors="ignore")
        duplicate = contents.get(body)
        assert duplicate is None, f"{path.stem} and {duplicate} have identical flag artwork"
        contents[body] = path.stem
