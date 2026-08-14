"""
Tests for the anonymous feedback endpoint.

Two things matter here and are easy to regress:

  1. *Nothing* is required. A visitor must be able to send a rating alone, a
     comment alone, or both, with no email and no account. If a future change
     makes email or comment mandatory, these fail.
  2. Nothing identifying is persisted. The insert must carry only what the
     visitor typed — no user id, IP or user-agent — so the table cannot be
     joined back to a person.

The DB is faked; these assert the request contract and the exact SQL
parameters, not Postgres behaviour. The RLS posture (INSERT-only for anon, no
SELECT) is enforced by the migration and verified against the live database.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import feedback as feedback_module
from app.db.database import get_db
from app.main import app


class _RecordingSession:
    """Captures the parameters handed to execute() so the test can assert on
    exactly what would be written."""

    def __init__(self):
        self.executed: list[tuple[str, dict]] = []
        self.committed = False

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


def _install_fakes(session: _RecordingSession):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override

    # The limiter needs a real bucket table; bypass it, it has its own tests.
    async def _no_rate_limit(*_args, **_kwargs):
        return None

    original = feedback_module.check_rate_limit
    feedback_module.check_rate_limit = _no_rate_limit
    return original


def _remove_fakes(original):
    app.dependency_overrides.pop(get_db, None)
    feedback_module.check_rate_limit = original


async def _post(payload: dict, session: _RecordingSession):
    original = _install_fakes(session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/feedback", json=payload)
    finally:
        _remove_fakes(original)


@pytest.mark.asyncio
async def test_rating_only_submission_is_accepted():
    session = _RecordingSession()
    response = await _post({"rating": 5}, session)
    assert response.status_code == 201
    assert session.committed
    _, params = session.executed[0]
    assert params["rating"] == 5
    assert params["comment"] is None and params["email"] is None


@pytest.mark.asyncio
async def test_comment_only_submission_is_accepted_without_email():
    session = _RecordingSession()
    response = await _post({"comment": "The bracket is great."}, session)
    assert response.status_code == 201
    _, params = session.executed[0]
    assert params["comment"] == "The bracket is great."
    assert params["rating"] is None
    assert params["email"] is None, "email must never be required"


@pytest.mark.asyncio
async def test_blank_strings_are_stored_as_null_not_empty_text():
    """The form posts "" for untouched fields; "no email given" must be NULL
    so it is distinguishable from an empty submission."""
    session = _RecordingSession()
    response = await _post({"rating": 4, "comment": "   ", "email": "  "}, session)
    assert response.status_code == 201
    _, params = session.executed[0]
    assert params["comment"] is None
    assert params["email"] is None


@pytest.mark.asyncio
async def test_empty_submission_is_rejected():
    session = _RecordingSession()
    response = await _post({"email": "someone@example.com"}, session)
    assert response.status_code == 422
    assert not session.executed, "nothing should be written for an empty submission"


@pytest.mark.asyncio
async def test_rating_must_be_within_one_to_five():
    for bad in (0, 6, -1):
        session = _RecordingSession()
        response = await _post({"rating": bad}, session)
        assert response.status_code == 422, f"rating {bad} should be rejected"


@pytest.mark.asyncio
async def test_obviously_invalid_email_is_rejected():
    session = _RecordingSession()
    response = await _post({"rating": 3, "email": "not-an-email"}, session)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_overlong_comment_is_rejected():
    session = _RecordingSession()
    response = await _post({"comment": "x" * 2001}, session)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_no_identifying_data_is_persisted():
    """The insert must carry only the four visitor-supplied fields — adding an
    IP or user-agent column later should force a deliberate decision, not slip
    in unnoticed."""
    session = _RecordingSession()
    response = await _post(
        {"rating": 5, "comment": "Nice", "email": "a@b.com", "page": "/tournaments"},
        session,
    )
    assert response.status_code == 201
    sql, params = session.executed[0]
    assert set(params) == {"rating", "comment", "email", "page"}
    lowered = sql.lower()
    for forbidden in ("ip_address", "user_agent", "user_id", "session"):
        assert forbidden not in lowered, f"{forbidden} must not be written"


@pytest.mark.asyncio
async def test_feedback_endpoint_requires_no_authentication():
    """No Authorization header is sent anywhere in this module; a 401/403 here
    would mean the endpoint had been put behind auth."""
    session = _RecordingSession()
    response = await _post({"rating": 4}, session)
    assert response.status_code not in (401, 403)
