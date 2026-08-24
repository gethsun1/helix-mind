import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.knowledge import extract_investigation_knowledge, investigation_graph
from app.knowledge_extraction import DeterministicKnowledgeExtractor
from app.models import Claim, Entity, Evidence, Investigation, InvestigationPaper, Paper, Relationship, User
from app.main import app


def _owner_id():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        return owner.id


def test_deterministic_extractor_keeps_exact_abstract_evidence() -> None:
    result = DeterministicKnowledgeExtractor().extract(
        title="CRISPR study",
        abstract="CRISPR targets HBB. The intervention was investigated for disease.",
        keywords=["CRISPR", "HBB"],
        mesh_terms=[],
    )
    assert [claim.text for claim in result.claims] == ["CRISPR targets HBB.", "The intervention was investigated for disease."]
    assert any(item.predicate == "TARGETS" for item in result.relationships)
    assert any(item.name == "HBB" and item.entity_type == "GENE" for item in result.entities)


def test_knowledge_persistence_is_provenance_preserving_and_idempotent() -> None:
    investigation_id = uuid.uuid4()
    paper_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(Investigation(id=investigation_id, owner_id=_owner_id(), title="Knowledge test", question="What targets HBB?", status="COMPLETED"))
        session.add(Paper(id=paper_id, source="PUBMED", external_id="knowledge-test", title="CRISPR study", abstract="CRISPR targets HBB.", authors=["Author"], publication_date=date(2024, 1, 1), pmid="knowledge-test", url="https://pubmed.ncbi.nlm.nih.gov/knowledge-test/", paper_metadata={"source_records": ["PUBMED"], "source_identifiers": {"PUBMED": "knowledge-test"}}))
        session.flush()
        session.add(InvestigationPaper(investigation_id=investigation_id, paper_id=paper_id, source="PUBMED", source_query="CRISPR"))
        session.commit()
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            first = extract_investigation_knowledge(session, investigation)
            second = extract_investigation_knowledge(session, investigation)
            assert first["claims"] == second["claims"] == 1
            assert session.scalar(select(Claim).where(Claim.investigation_id == investigation_id)) is not None
            assert session.scalar(select(Evidence).where(Evidence.investigation_id == investigation_id)) is not None
            assert session.scalar(select(Entity).where(Entity.entity_type == "GENE", Entity.normalized_name == "hbb")) is not None
            assert session.scalar(select(Relationship).where(Relationship.investigation_id == investigation_id, Relationship.predicate == "TARGETS")) is not None
            graph = investigation_graph(session, investigation_id)
            assert graph["nodes"]
            assert graph["edges"]
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
            paper = session.get(Paper, paper_id)
            if paper:
                session.delete(paper)
            session.commit()


def test_knowledge_api_requires_authentication(monkeypatch) -> None:
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", "knowledge-api-test-secret")
    get_settings.cache_clear()
    response = TestClient(app).get(f"/api/v1/investigations/{uuid.uuid4()}/knowledge")
    assert response.status_code == 401
