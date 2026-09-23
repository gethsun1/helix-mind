import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.literature import build_search_strategy
from app.main import app
from app.models import Investigation, User


def _user_id():
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert user is not None
        return user.id


def _client(monkeypatch, user_id):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", "research-memory-focused-test-secret")
    get_settings.cache_clear()
    token = jwt.encode({"sub": str(user_id)}, get_settings().auth_secret, algorithm="HS256")
    return TestClient(app), {"Authorization": f"Bearer {token}"}


def test_memory_persists_is_owner_scoped_and_deactivates(monkeypatch):
    owner_id = _user_id()
    investigation_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(User(id=other_user_id, email=f"memory-isolation-{other_user_id}@example.invalid", name="Other researcher"))
        session.add(Investigation(id=investigation_id, owner_id=owner_id, title="Memory test", question="How does memory change research?", status="COMPLETED"))
        session.commit()
    try:
        client, headers = _client(monkeypatch, owner_id)
        created = client.post(f"/api/v1/investigations/{investigation_id}/memories", headers=headers, json={"memory_type": "HUMAN_CLINICAL_PRIORITY", "decision_text": "Prioritize human clinical evidence."})
        assert created.status_code == 201, created.text
        memory = created.json()
        assert memory["active"] is True
        assert memory["metadata"]["decision_origin"] == "explicit_user_save"

        # A fresh API request/client session reads the persisted PostgreSQL row.
        fresh_client, fresh_headers = _client(monkeypatch, owner_id)
        listed = fresh_client.get(f"/api/v1/investigations/{investigation_id}/memories", headers=fresh_headers)
        assert listed.status_code == 200 and listed.json()[0]["id"] == memory["id"]

        _, other_headers = _client(monkeypatch, other_user_id)
        assert fresh_client.get(f"/api/v1/investigations/{investigation_id}/memories", headers=other_headers).status_code == 404

        deactivated = fresh_client.post(f"/api/v1/investigations/{investigation_id}/memories/{memory['id']}/deactivate", headers=fresh_headers)
        assert deactivated.status_code == 200
        assert deactivated.json()["active"] is False
        assert deactivated.json()["deactivated_at"]
    finally:
        with SessionLocal() as session:
            row = session.get(Investigation, investigation_id)
            if row:
                session.delete(row)
            other_user = session.get(User, other_user_id)
            if other_user:
                session.delete(other_user)
            session.commit()
        get_settings.cache_clear()


def test_human_clinical_memory_changes_actual_retrieval_queries_and_plan():
    plan = {
        "key_concepts": ["CRISPR", "HBB", "sickle-cell disease"],
        "memory_policy": {"memory_ids": [str(uuid.uuid4())], "prioritize_human_clinical": True},
        "evidence_categories": [],
    }
    strategy = build_search_strategy(plan, "CRISPR for sickle-cell disease")
    assert "Humans[MeSH Terms]" in strategy["pubmed"]
    assert "clinical trial" in strategy["europe_pmc"]


def test_worker_persists_applied_memory_in_run_manifest_and_audit(monkeypatch):
    from app import jobs
    from app.models import InvestigationEvent, InvestigationRun, ResearchMemory
    from app.research_reproducibility import create_run

    owner_id = _user_id()
    investigation_id = uuid.uuid4()
    with SessionLocal() as session:
        investigation = Investigation(id=investigation_id, owner_id=owner_id, title="Memory influence test", question="How does a saved decision alter later research?", status="QUEUED")
        session.add(investigation)
        session.flush()
        memory = ResearchMemory(owner_id=owner_id, investigation_id=investigation_id, memory_type="HUMAN_CLINICAL_PRIORITY", decision_text="Prioritize human clinical evidence.", audit_metadata={"decision_origin": "explicit_user_save"})
        session.add(memory)
        session.flush()
        run = create_run(session, investigation)
        run_id = run.id
        memory_id = memory.id
        session.commit()

    monkeypatch.setattr(jobs, "run_research_planning", lambda **_: {"research_objectives": [], "research_questions": [], "search_strategies": [], "key_concepts": ["CRISPR"], "evidence_categories": [], "reasoning_tasks": [], "_metadata": {}})
    monkeypatch.setattr(jobs, "run_literature_pipeline", lambda *_: {"paper_count": 0})
    monkeypatch.setattr(jobs, "extract_investigation_knowledge", lambda *_: {"papers": 0})
    monkeypatch.setattr(jobs, "freeze_snapshot", lambda *_args, **_kwargs: None)
    try:
        result = jobs.start_investigation(str(investigation_id), str(run_id))
        assert result["status"] == "COMPLETED"
        with SessionLocal() as session:
            run = session.get(InvestigationRun, run_id)
            assert run is not None
            assert run.input_manifest["research_memories"][0]["id"] == str(memory_id)
            assert run.input_manifest["applied_memory_policy"]["prioritize_human_clinical"] is True
            event = session.scalar(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation_id, InvestigationEvent.event_type == "research_memory_applied"))
            assert event is not None
            assert str(memory_id) in event.event_metadata["memory_ids"]
    finally:
        with SessionLocal() as session:
            row = session.get(Investigation, investigation_id)
            if row:
                session.delete(row)
            session.commit()
