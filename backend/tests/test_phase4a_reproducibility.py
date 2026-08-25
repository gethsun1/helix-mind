import uuid
from datetime import date, datetime, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Investigation, InvestigationPaper, InvestigationRun, Paper, ResearchSnapshot, User
from app.research_reproducibility import compare_snapshots, create_run, digest_json, freeze_snapshot


TEST_SECRET = "phase4a-reproducibility-secret"


def _owner_id():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        return owner.id


def _token(user_id):
    return jwt.encode({"sub": str(user_id)}, TEST_SECRET, algorithm="HS256")


def _completed_investigation():
    investigation_id = uuid.uuid4()
    paper_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(Investigation(id=investigation_id, owner_id=_owner_id(), title="Phase 4A snapshot test", question="What source records support a reproducible research snapshot?", domain="biotechnology", status="COMPLETED", completed_at=datetime.now(timezone.utc)))
        session.add(Paper(id=paper_id, source="PUBMED", external_id=f"phase4a-{paper_id}", title="Snapshot source", abstract="A source abstract.", authors=["Author"], publication_date=date(2025, 1, 1), pmid=f"phase4a-{paper_id}", url="https://pubmed.ncbi.nlm.nih.gov/phase4a/"))
        session.flush()
        session.add(InvestigationPaper(investigation_id=investigation_id, paper_id=paper_id, source="PUBMED", source_query="snapshot test"))
        session.commit()
    return investigation_id, paper_id


def _cleanup(investigation_id, paper_id):
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        if investigation:
            session.delete(investigation)
        paper = session.get(Paper, paper_id)
        if paper:
            session.delete(paper)
        session.commit()


def test_snapshot_is_idempotent_hashed_and_source_complete() -> None:
    investigation_id, paper_id = _completed_investigation()
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            run = create_run(session, investigation, status="COMPLETED")
            run.started_at = investigation.created_at
            run.completed_at = investigation.completed_at
            first = freeze_snapshot(session, investigation, run, created_by_user_id=_owner_id())
            second = freeze_snapshot(session, investigation, run, created_by_user_id=_owner_id())
            session.commit()

            assert first.id == second.id
            assert first.manifest_digest == digest_json(first.manifest)
            assert first.manifest["papers"][0]["id"] == str(paper_id)
            assert first.manifest["artifact_contract"]["supported_formats"] == ["markdown", "scientific_report", "obsidian_vault"]
            assert all(isinstance(item, str) for item in first.manifest["papers"][0].keys())
    finally:
        _cleanup(investigation_id, paper_id)


def test_snapshot_comparison_reports_added_records_without_mutating_parent() -> None:
    investigation_id, paper_id = _completed_investigation()
    second_paper_id = uuid.uuid4()
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            first_run = create_run(session, investigation, status="COMPLETED")
            first_run.completed_at = datetime.now(timezone.utc)
            first_snapshot = freeze_snapshot(session, investigation, first_run)
            session.commit()

            session.add(Paper(id=second_paper_id, source="EUROPE_PMC", external_id=f"phase4a-second-{second_paper_id}", title="Second snapshot source", abstract="A later source abstract.", authors=["Author B"], publication_date=date(2025, 2, 1), pmcid=f"PMC{str(second_paper_id).replace('-', '')[:8].upper()}"))
            session.flush()
            session.add(InvestigationPaper(investigation_id=investigation_id, paper_id=second_paper_id, source="EUROPE_PMC", source_query="snapshot test 2"))
            second_run = create_run(session, investigation, parent_run_id=first_run.id, status="COMPLETED")
            second_run.completed_at = datetime.now(timezone.utc)
            second_snapshot = freeze_snapshot(session, investigation, second_run)
            comparison = compare_snapshots(first_snapshot, second_snapshot)
            session.commit()

            assert comparison["sections"]["papers"]["added_ids"] == [str(second_paper_id)]
            assert comparison["sections"]["papers"]["removed_ids"] == []
            assert comparison["summary"]["added"] >= 1
            assert first_snapshot.manifest["papers"] != second_snapshot.manifest["papers"]
            assert first_snapshot.manifest_digest != second_snapshot.manifest_digest
    finally:
        _cleanup(investigation_id, paper_id)
        with SessionLocal() as session:
            paper = session.get(Paper, second_paper_id)
            if paper:
                session.delete(paper)
            session.commit()


def test_reproducibility_api_queues_owner_scoped_rerun_and_compares_snapshots(monkeypatch) -> None:
    investigation_id, paper_id = _completed_investigation()

    class FakeQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, function, *args):
            self.calls.append((function, args))
            return object()

    queue = FakeQueue()
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    from app.routes import reproducibility as reproducibility_routes
    monkeypatch.setattr(reproducibility_routes, "get_research_queue", lambda: queue)

    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            run = create_run(session, investigation, status="COMPLETED")
            run.completed_at = datetime.now(timezone.utc)
            snapshot = freeze_snapshot(session, investigation, run)
            run_id = run.id
            snapshot_id = snapshot.id
            snapshot_digest = snapshot.manifest_digest
            session.commit()

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {_token(_owner_id())}"}
        rerun = client.post(f"/api/v1/investigations/{investigation_id}/runs", headers=headers)
        assert rerun.status_code == 202
        assert rerun.json()["status"] == "QUEUED"
        assert rerun.json()["parentRunId"] == str(run_id)
        assert queue.calls and queue.calls[0][1][0] == str(investigation_id)

        runs = client.get(f"/api/v1/investigations/{investigation_id}/runs", headers=headers)
        snapshots = client.get(f"/api/v1/investigations/{investigation_id}/snapshots", headers=headers)
        comparison = client.get(f"/api/v1/investigations/{investigation_id}/snapshots/compare?leftSnapshotId={snapshot_id}&rightSnapshotId={snapshot_id}", headers=headers)
        assert runs.status_code == 200 and len(runs.json()) == 2
        assert snapshots.status_code == 200 and snapshots.json()[0]["manifestDigest"] == snapshot_digest
        assert comparison.status_code == 200 and comparison.json()["summary"] == {"added": 0, "removed": 0, "changed": 0}
    finally:
        _cleanup(investigation_id, paper_id)
