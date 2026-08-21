from uuid import UUID

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Investigation, User

TEST_SECRET = "phase3a-test-secret"
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000001")


def token_for(user_id: UUID) -> str:
    return jwt.encode({"sub": str(user_id)}, TEST_SECRET, algorithm="HS256")


def test_unauthorized_and_admin_access_are_server_enforced(monkeypatch) -> None:
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    monkeypatch.setenv("HELIXMIND_AUTH_SYNC_SECRET", "phase3a-sync-secret")
    get_settings.cache_clear()
    client = TestClient(app)

    assert client.get("/api/v1/me").status_code == 401
    admin_response = client.get(
        "/api/v1/admin/diagnostics", headers={"Authorization": f"Bearer {token_for(ADMIN_ID)}"}
    )
    assert admin_response.status_code == 200
    assert "GEMINI_API_KEY" not in admin_response.text
    assert "GROQ_API_KEY" not in admin_response.text


def test_normal_user_cannot_access_admin_or_another_users_investigation(monkeypatch) -> None:
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    with SessionLocal() as session:
        investigation = session.scalar(select(Investigation).where(Investigation.owner_id == ADMIN_ID))
        assert investigation is not None
        outsider = User(email="phase3a-isolation@example.invalid", name="Isolation Test")
        session.add(outsider)
        session.commit()
        outsider_id = outsider.id
        investigation_id = investigation.id

    try:
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token_for(outsider_id)}"}
        assert client.get("/api/v1/admin/diagnostics", headers=headers).status_code == 403
        assert client.get(f"/api/v1/investigations/{investigation_id}", headers=headers).status_code == 404
        assert client.get("/api/v1/investigations", headers=headers).json() == []
    finally:
        with SessionLocal() as session:
            user = session.get(User, outsider_id)
            if user:
                session.delete(user)
                session.commit()
