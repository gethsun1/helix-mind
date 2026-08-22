import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.jobs import start_investigation
from app.main import app
from app.models import Investigation, InvestigationEvent, User
from app.omegaclaw_planning import OmegaClawPlanningError


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[object, str]] = []

    def enqueue(self, function: object, investigation_id: str) -> object:
        self.enqueued.append((function, investigation_id))
        return object()


def _owner_id():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        return owner.id


def test_create_investigation_queues_owner_scoped_job(monkeypatch) -> None:
    from app.routes import investigations as investigation_routes

    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", "phase3b-test-secret")
    get_settings.cache_clear()
    queue = FakeQueue()
    monkeypatch.setattr(investigation_routes, "get_research_queue", lambda: queue)
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        token = jwt.encode({"sub": str(owner.id)}, "phase3b-test-secret", algorithm="HS256")
    response = TestClient(app).post(
        "/api/v1/investigations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "CRISPR planning test",
            "researchQuestion": "What is the evidence for CRISPR treatment of sickle-cell disease?",
            "domain": "Medicine",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert "createdAt" in body
    assert len(queue.enqueued) == 1

    with SessionLocal() as session:
        investigation = session.get(Investigation, uuid.UUID(body["id"]))
        assert investigation is not None
        assert investigation.owner_id == _owner_id()
        assert investigation.title == "CRISPR planning test"
        assert investigation.domain == "medicine"
        assert investigation.question.startswith("What is the evidence")
        assert session.scalar(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation.id))
        session.delete(investigation)
        session.commit()


def _create_queued() -> uuid.UUID:
    with SessionLocal() as session:
        investigation = Investigation(
            owner_id=_owner_id(),
            title="Worker lifecycle test",
            question="How should a worker persist a research plan safely?",
            domain="biotechnology",
            status="QUEUED",
        )
        session.add(investigation)
        session.commit()
        return investigation.id


def test_worker_persists_real_planning_result(monkeypatch) -> None:
    from app import jobs

    investigation_id = _create_queued()
    plan = {
        "research_objectives": ["Objective"],
        "research_questions": ["Question"],
        "search_strategies": ["Strategy"],
        "key_concepts": ["Concept"],
        "evidence_categories": ["Category"],
        "reasoning_tasks": ["Task"],
        "_metadata": {"orchestrator": "OmegaClaw", "provider": "groq", "model": "test"},
    }
    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: plan)
    assert start_investigation(str(investigation_id)) == {"status": "PLANNING", "plan": "persisted"}
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.status == "PLANNING"
        assert investigation.research_plan == plan
        event_types = session.scalars(select(InvestigationEvent.event_type).where(InvestigationEvent.investigation_id == investigation_id)).all()
        assert event_types == ["research_started", "planning_started", "planning_completed"]
        session.delete(investigation)
        session.commit()


def test_worker_marks_provider_failure_without_leaking_details(monkeypatch) -> None:
    from app import jobs

    investigation_id = _create_queued()
    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: (_ for _ in ()).throw(OmegaClawPlanningError("provider unavailable", "EXTERNAL_PROVIDER_ERROR")))
    assert start_investigation(str(investigation_id)) == {"status": "FAILED"}
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.status == "FAILED"
        assert investigation.error_message == "provider unavailable"
        failure = session.scalar(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation_id, InvestigationEvent.event_type == "investigation_failed"))
        assert failure is not None
        assert failure.event_metadata == {"category": "EXTERNAL_PROVIDER_ERROR"}
        session.delete(investigation)
        session.commit()
