"""`next dev` falls back to port 3001 when 3000 is taken; the API must allow it."""
from fastapi.testclient import TestClient

from app.main import app

DEV_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]


def test_dev_frontend_origins_are_allowed():
    client = TestClient(app)
    for origin in DEV_ORIGINS:
        r = client.get("/health", headers={"Origin": origin})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin
