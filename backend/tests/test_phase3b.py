import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.jobs import start_investigation
from app.main import app
from app.models import Investigation, InvestigationEvent, InvestigationRun, ResearchMemory, ResearchSnapshot, User
from app.omegaclaw_planning import OmegaClawPlanningError
from app.research_planning import deterministic_fallback_plan


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
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        session.add(ResearchMemory(
            owner_id=investigation.owner_id,
            investigation_id=investigation.id,
            memory_type="HUMAN_CLINICAL_PRIORITY",
            decision_text="Prioritize human clinical evidence.",
            active=True,
        ))
        session.commit()
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
    monkeypatch.setattr(jobs, "run_literature_pipeline", lambda session, investigation: {"paper_count": 0, "normalized_count": 0, "duplicates_removed": 0, "failures": {}, "partial": False})
    result = start_investigation(str(investigation_id))
    assert result["status"] == "COMPLETED"
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.status == "COMPLETED"
        assert investigation.research_plan == plan
        assert investigation.research_plan["memory_policy"]["prioritize_human_clinical"] is True
        assert any("Human clinical evidence prioritized" in item for item in investigation.research_plan["evidence_categories"])
        event_types = session.scalars(select(InvestigationEvent.event_type).where(InvestigationEvent.investigation_id == investigation_id)).all()
        assert event_types[:5] == ["research_started", "planning_started", "research_memory_applied", "planning_completed", "literature_search_started"]
        assert event_types[-2:] == ["metta_validation_skipped", "knowledge_extraction_completed"]
        session.delete(investigation)
        session.commit()


def test_worker_recovers_from_provider_failure_with_degraded_plan(monkeypatch) -> None:
    from app import jobs

    investigation_id = _create_queued()
    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: (_ for _ in ()).throw(OmegaClawPlanningError("provider unavailable", "EXTERNAL_PROVIDER_ERROR")))
    monkeypatch.setattr(jobs, "run_literature_pipeline", lambda *_: {"paper_count": 0, "normalized_count": 0, "duplicates_removed": 0, "failures": {}, "partial": False})
    monkeypatch.setattr(jobs, "extract_investigation_knowledge", lambda *_: {"papers": 0})
    assert start_investigation(str(investigation_id))["status"] == "COMPLETED"
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.status == "COMPLETED"
        assert investigation.research_plan["_metadata"]["orchestrator"] == "deterministic_fallback"
        degraded = session.scalar(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation_id, InvestigationEvent.event_type == "planning_degraded"))
        assert degraded is not None
        assert degraded.message == "OmegaClaw planning unavailable; deterministic research plan used."
        session.delete(investigation)
        session.commit()


def test_deterministic_fallback_plan_contains_search_instructions_not_findings() -> None:
    plan = deterministic_fallback_plan(
        title="CRISPR in lung cancer",
        research_question="What is the current evidence on CRISPR in lung cancer?",
        domain="oncology",
        failure_category="timeout",
    )
    assert plan["key_concepts"][:2] == ["CRISPR lung cancer", "CRISPR"]
    assert "lung cancer" in plan["key_concepts"]
    assert plan["_metadata"] == {
        "orchestrator": "deterministic_fallback",
        "planning_status": "DEGRADED",
        "provider": "none",
        "model": "none",
        "trigger": "timeout",
    }
    assert "not a scientific conclusion" in plan["source_note"]


def test_worker_continues_to_literature_with_degraded_plan_and_applies_memory(monkeypatch) -> None:
    from app import jobs

    investigation_id = _create_queued()
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        session.add(ResearchMemory(
            owner_id=investigation.owner_id,
            investigation_id=investigation.id,
            memory_type="HUMAN_CLINICAL_PRIORITY",
            decision_text="Prioritize human clinical evidence.",
            active=True,
        ))
        session.commit()

    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: (_ for _ in ()).throw(OmegaClawPlanningError("planner unavailable", "EXTERNAL_PROVIDER_ERROR")))
    observed = {}

    def literature(session, investigation):
        observed["plan"] = dict(investigation.research_plan)
        return {"paper_count": 0, "normalized_count": 0, "duplicates_removed": 0, "failures": {}, "partial": False}

    monkeypatch.setattr(jobs, "run_literature_pipeline", literature)
    monkeypatch.setattr(jobs, "extract_investigation_knowledge", lambda *_: {"papers": 0})
    result = jobs.start_investigation(str(investigation_id))
    assert result["status"] == "COMPLETED"
    assert observed["plan"]["_metadata"]["orchestrator"] == "deterministic_fallback"
    assert observed["plan"]["memory_policy"]["prioritize_human_clinical"] is True
    assert any("Human clinical evidence prioritized" in item for item in observed["plan"]["evidence_categories"])
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.investigation_id == investigation_id))
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.investigation_id == investigation_id))
        events = session.scalars(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation_id)).all()
        assert investigation is not None and investigation.status == "COMPLETED"
        assert run is not None and run.plan_hash
        assert snapshot is not None
        assert any(event.event_type == "planning_degraded" for event in events)
        assert any(event.event_type == "research_memory_applied" for event in events)
        session.delete(investigation)
        session.commit()


def test_worker_records_timeout_as_degraded_and_continues(monkeypatch) -> None:
    from app import jobs

    investigation_id = _create_queued()
    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: (_ for _ in ()).throw(OmegaClawPlanningError("OmegaClaw planning timed out.", "OMEGACLAW_TIMEOUT")))
    reached_literature = []
    monkeypatch.setattr(jobs, "run_literature_pipeline", lambda *_: reached_literature.append(True) or {"paper_count": 0, "normalized_count": 0, "duplicates_removed": 0, "failures": {}, "partial": False})
    monkeypatch.setattr(jobs, "extract_investigation_knowledge", lambda *_: {"papers": 0})
    assert jobs.start_investigation(str(investigation_id))["status"] == "COMPLETED"
    assert reached_literature == [True]
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.research_plan["_metadata"]["trigger"] == "OMEGACLAW_TIMEOUT"
        session.delete(investigation)
        session.commit()
