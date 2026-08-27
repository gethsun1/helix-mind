import json
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from zipfile import ZipFile
from io import BytesIO

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import SessionLocal
from app.jobs import generate_research_artifact
from app.main import app
from app.models import Investigation, ResearchArtifact
from app.research_artifacts import GENERATOR_VERSION, build_markdown, build_obsidian_files, build_obsidian_zip, build_scientific_report, generate_artifact
from app.research_reproducibility import create_run, freeze_snapshot

from test_phase4a_reproducibility import TEST_SECRET, _cleanup, _completed_investigation, _owner_id


def _snapshot():
    paper_id = "paper-1"
    proposition_id = "proposition-1"
    evidence_id = "evidence-1"
    hypothesis_id = "hypothesis-1"
    return SimpleNamespace(
        id="snapshot-1",
        investigation_id="investigation-1",
        run_id="run-1",
        snapshot_number=1,
        schema_version="phase4a-1",
        formula_version="3E-1",
        metta_digest="metta-digest",
        manifest_digest="manifest-digest",
        created_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        manifest={
            "investigation": {"title": "CRISPR / HBB study", "question": "What evidence supports targeting HBB?", "domain": "biotechnology", "research_plan": {"key_concepts": ["CRISPR", "HBB"]}},
            "run": {"id": "run-1", "run_number": 1, "status": "COMPLETED"},
            "papers": [{"id": paper_id, "source": "PUBMED", "external_id": "123", "title": "A source paper", "abstract": "A source abstract.", "authors": ["Author One"], "journal": "Research Journal", "publication_date": "2026-01-01", "doi": "10.1000/example", "pmid": "123", "pmcid": None, "url": "https://pubmed.ncbi.nlm.nih.gov/123/", "retrieved_at": "2026-08-27T00:00:00+00:00"}],
            "searches": [{"id": "search-1", "source": "PUBMED", "query": "CRISPR HBB", "status": "SUCCEEDED"}],
            "claims": [],
            "evidence": [{"id": evidence_id, "paper_id": paper_id, "proposition_id": proposition_id, "evidence_type": "ABSTRACT", "extracted_text": "CRISPR targets HBB.", "source_location": "abstract", "source_span": {"start": 0, "end": 20}, "polarity": "SUPPORTS", "extraction_method": "deterministic_abstract", "confidence": "0.800", "strength": "0.600"}],
            "entities": [],
            "relationships": [],
            "propositions": [{"id": proposition_id, "subject": "CRISPR", "predicate": "TARGETS", "object": "HBB", "description": "CRISPR targets HBB."}],
            "hypotheses": [{"id": hypothesis_id, "proposition_id": proposition_id, "statement": "CRISPR targets HBB.", "status": "WEAK", "confidence": "0.400", "supporting_evidence_count": 1, "contradictory_evidence_count": 0}],
            "inferences": [{"id": "inference-1", "hypothesis_id": hypothesis_id, "rule_name": "direct_evidence_balance", "reasoning_summary": "Available evidence is supportive."}],
            "contradictions": [],
            "knowledge_gaps": [],
            "provider_metadata": [],
            "events": [],
        },
    )


def test_structured_report_preserves_snapshot_provenance_and_distinctions() -> None:
    report = build_scientific_report(_snapshot())
    assert report["generated_from"] == "immutable_research_snapshot"
    assert report["reproducibility"]["manifest_digest"] == "manifest-digest"
    assert report["evidence"][0]["extracted_text"] == "CRISPR targets HBB."
    assert report["reasoning"]["confidence_semantics"].startswith("HelixMind evidence confidence")
    assert report["references"][0]["doi"] == "10.1000/example"


def test_markdown_is_deterministic_and_contains_source_links() -> None:
    first = build_markdown(_snapshot())
    second = build_markdown(_snapshot())
    assert first == second
    assert "[[Paper-paper-1]]" in first
    assert "[[Proposition-proposition-1]]" in first
    assert "Evidence confidence" in first
    assert "not semantic certainty" in first


def test_obsidian_vault_has_stable_structure_and_wikilinks() -> None:
    files = build_obsidian_files(_snapshot())
    names = set(files)
    assert any(name.endswith("/README.md") for name in names)
    assert any(name.endswith("/README.md") for name in names)
    assert any("/Literature/Paper-paper-1.md" in name for name in names)
    hypothesis = next(content for name, content in files.items() if "/Hypotheses/" in name)
    assert "[[Proposition-proposition-1]]" in hypothesis
    assert "[[Evidence-evidence-1]]" in hypothesis
    with ZipFile(BytesIO(build_obsidian_zip(_snapshot()))) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(".." not in name for name in archive.namelist())
        assert "Manifest/report.json" in "\n".join(archive.namelist())


def test_artifact_formats_have_expected_media_and_generator_metadata() -> None:
    markdown = generate_artifact(_snapshot(), "MARKDOWN")
    report = generate_artifact(_snapshot(), "SCIENTIFIC_REPORT")
    vault = generate_artifact(_snapshot(), "OBSIDIAN_VAULT")
    assert markdown.artifact_type == "RESEARCH_MARKDOWN"
    assert markdown.content_type == "text/markdown"
    assert report.content_type == "application/json"
    assert json.loads(report.content)["artifact_type"] == "SCIENTIFIC_REPORT"
    assert vault.content_type == "application/zip"
    assert GENERATOR_VERSION == "phase4b-1"


def test_worker_persists_private_artifact_content_and_is_idempotent(tmp_path, monkeypatch) -> None:
    investigation_id, paper_id = _completed_investigation()
    monkeypatch.setattr(get_settings(), "artifact_root", str(tmp_path))
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            run = create_run(session, investigation, status="COMPLETED")
            run.completed_at = datetime.now(timezone.utc)
            snapshot = freeze_snapshot(session, investigation, run)
            artifact = ResearchArtifact(
                snapshot_id=snapshot.id,
                artifact_type="RESEARCH_MARKDOWN",
                artifact_format="markdown",
                status="QUEUED",
                generator_version=GENERATOR_VERSION,
                schema_version="phase4a-1",
                manifest_digest=snapshot.manifest_digest,
                visibility="PRIVATE",
            )
            session.add(artifact)
            session.commit()
            artifact_id = artifact.id

        first = generate_research_artifact(str(artifact_id))
        second = generate_research_artifact(str(artifact_id))
        assert first["status"] == "COMPLETED"
        assert second["status"] == "COMPLETED"
        with SessionLocal() as session:
            stored = session.get(ResearchArtifact, artifact_id)
            assert stored is not None
            assert stored.status == "COMPLETED"
            assert stored.storage_key is not None
            content_path = tmp_path / stored.storage_key
            content = content_path.read_bytes()
            assert stored.file_size == len(content)
            assert stored.content_digest == hashlib.sha256(content).hexdigest()
            assert stored.visibility == "PRIVATE"
    finally:
        _cleanup(investigation_id, paper_id)


def test_artifact_api_is_owner_scoped_and_deduplicates_queue_requests(monkeypatch) -> None:
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
            session.commit()
            snapshot_id = snapshot.id

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {jwt.encode({'sub': str(_owner_id())}, TEST_SECRET, algorithm='HS256')}"}
        investigation_response = client.get(f"/api/v1/investigations/{investigation_id}", headers=headers)
        assert investigation_response.status_code == 200
        assert investigation_response.json()["health"]["papers"] == 1
        assert len(investigation_response.json()["milestones"]) == 8
        first = client.post(
            f"/api/v1/investigations/{investigation_id}/snapshots/{snapshot_id}/artifacts",
            headers=headers,
            json={"artifactType": "MARKDOWN"},
        )
        second = client.post(
            f"/api/v1/investigations/{investigation_id}/snapshots/{snapshot_id}/artifacts",
            headers=headers,
            json={"artifactType": "MARKDOWN"},
        )
        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        assert len(queue.calls) == 1
        assert queue.calls[0][1][0] == str(first.json()["id"])

        listed = client.get(
            f"/api/v1/investigations/{investigation_id}/snapshots/{snapshot_id}/artifacts",
            headers=headers,
        )
        assert listed.status_code == 200
        assert listed.json()[0]["downloadUrl"] is None
    finally:
        _cleanup(investigation_id, paper_id)
