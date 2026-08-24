import uuid
from datetime import date

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.literature import EUROPE_PMC, PUBMED, LiteratureError, NormalizedPaper, SourceSearchResult, deduplicate_papers
from app.literature_pipeline import LiteraturePipelineError, run_literature_pipeline
from app.main import app
from app.models import Investigation, InvestigationEvent, InvestigationPaper, Paper, ResearchSearch, User


def _owner_id():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        return owner.id


def _candidate(source: str, external_id: str, *, doi: str | None = None, pmid: str | None = None) -> NormalizedPaper:
    return NormalizedPaper(
        source=source,
        external_id=external_id,
        title="CRISPR therapy for sickle-cell disease",
        abstract="CRISPR evidence from the source.",
        authors=["Researcher A"],
        publication_date=date(2024, 1, 2),
        doi=doi,
        url="https://example.invalid/source",
        pmid=pmid,
        metadata={"search_query": "plan query", "source_records": [source]},
    )


def test_deduplication_prefers_identifier_hierarchy() -> None:
    first = _candidate(PUBMED, "12345", doi="10.1000/example", pmid="12345")
    second = _candidate(EUROPE_PMC, "pmc:PMC123", doi="10.1000/example", pmid="12345")
    unique, removed = deduplicate_papers([first, second])
    assert len(unique) == 1
    assert removed == 1
    assert unique[0].source == PUBMED
    assert set(unique[0].metadata["source_records"]) == {PUBMED, EUROPE_PMC}


def test_deduplication_prefers_pmid_before_doi() -> None:
    first = _candidate(PUBMED, "12345", doi="10.1000/first", pmid="12345")
    second = _candidate(EUROPE_PMC, "pmc:PMC123", doi="10.1000/second", pmid="12345")
    unique, removed = deduplicate_papers([first, second])
    assert removed == 1
    assert unique[0].pmid == "12345"


def test_literature_pipeline_persists_searches_links_and_rank(monkeypatch) -> None:
    from app import literature_pipeline

    investigation_id = uuid.uuid4()
    with SessionLocal() as session:
        investigation = Investigation(
            id=investigation_id,
            owner_id=_owner_id(),
            title="Phase 3C pipeline test",
            question="What is the evidence for CRISPR therapy in sickle-cell disease?",
            domain="medicine",
            status="SEARCHING",
            research_plan={"key_concepts": ["CRISPR", "sickle-cell disease"], "research_questions": ["Question"]},
        )
        session.add(investigation)
        session.commit()

    class FakeClient:
        def __init__(self):
            pass

        def close(self):
            pass

        def search_pubmed_result(self, query, **kwargs):
            return SourceSearchResult(PUBMED, query, [_candidate(PUBMED, "12345", doi="10.1000/example", pmid="12345")], 1)

        def search_europe_pmc_result(self, query, **kwargs):
            return SourceSearchResult(EUROPE_PMC, query, [_candidate(EUROPE_PMC, "pmc:PMC123", doi="10.1000/example", pmid="12345")], 1)

    monkeypatch.setattr(literature_pipeline, "LiteratureClient", FakeClient)
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            summary = run_literature_pipeline(session, investigation)
            assert summary["paper_count"] == 1
            assert summary["duplicates_removed"] == 1
            assert summary["failures"] == {}
            searches = session.scalars(select(ResearchSearch).where(ResearchSearch.investigation_id == investigation_id)).all()
            assert {search.source for search in searches} == {PUBMED, EUROPE_PMC}
            assert all(search.status == "SUCCEEDED" for search in searches)
            link = session.scalar(select(InvestigationPaper).where(InvestigationPaper.investigation_id == investigation_id))
            assert link is not None
            assert link.relevance_score is not None
            assert link.rank == 1
            events = session.scalars(select(InvestigationEvent).where(InvestigationEvent.investigation_id == investigation_id).order_by(InvestigationEvent.timestamp.asc())).all()
            assert events[-1].event_type == "literature_search_completed"
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
            for paper in session.scalars(select(Paper).where(Paper.doi == "10.1000/example")).all():
                session.delete(paper)
            session.commit()


def test_authenticated_paginated_paper_api_and_detail(monkeypatch) -> None:
    investigation_id = uuid.uuid4()
    paper_id = uuid.uuid4()
    with SessionLocal() as session:
        investigation = Investigation(id=investigation_id, owner_id=_owner_id(), title="Paper API test", question="What is a paper API test question?", status="COMPLETED")
        paper = Paper(id=paper_id, source=PUBMED, external_id="api-test-pmid", title="API source paper", abstract="Source abstract.", authors=["Author"], pmid="api-test-pmid", publication_date=date(2023, 1, 1), url="https://pubmed.ncbi.nlm.nih.gov/api-test-pmid/")
        session.add_all([investigation, paper])
        session.flush()
        session.add(InvestigationPaper(investigation_id=investigation_id, paper_id=paper_id, source=PUBMED, source_query="CRISPR[Title/Abstract]", relevance_score=0.75, relevance_reason="Matched plan concepts.", rank=1))
        session.commit()
    try:
        monkeypatch.setenv("HELIXMIND_AUTH_SECRET", "phase3c-api-test-secret")
        get_settings.cache_clear()
        get_settings()
        token = jwt.encode({"sub": str(_owner_id())}, get_settings().auth_secret, algorithm="HS256")
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/api/v1/investigations/{investigation_id}/papers?pageSize=20", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "API source paper"
        detail = client.get(f"/api/v1/papers/{paper_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["investigations"][0]["title"] == "Paper API test"
        assert detail.json()["provenance"][0]["query"] == "CRISPR[Title/Abstract]"
        assert detail.json()["provenance"][0]["retrievalStatus"] == "UNKNOWN"
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
            paper = session.get(Paper, paper_id)
            if paper:
                session.delete(paper)
            session.commit()


def test_partial_source_failure_preserves_successful_literature(monkeypatch) -> None:
    from app import literature_pipeline

    investigation_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(Investigation(id=investigation_id, owner_id=_owner_id(), title="Partial provider test", question="What is partial literature evidence?", status="SEARCHING", research_plan={"key_concepts": ["CRISPR", "disease"]}))
        session.commit()

    class PartialClient:
        def close(self):
            pass

        def search_pubmed_result(self, query, **kwargs):
            raise LiteratureError("PubMed unavailable.")

        def search_europe_pmc_result(self, query, **kwargs):
            return SourceSearchResult(EUROPE_PMC, query, [_candidate(EUROPE_PMC, "partial:1", pmid="partial-1")], 1)

    monkeypatch.setattr(literature_pipeline, "LiteratureClient", PartialClient)
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            summary = run_literature_pipeline(session, investigation)
            assert summary["partial"] is True
            assert summary["paper_count"] == 1
            statuses = session.scalars(select(ResearchSearch.status).where(ResearchSearch.investigation_id == investigation_id)).all()
            assert sorted(statuses) == ["FAILED", "SUCCEEDED"]
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
            for paper in session.scalars(select(Paper).where(Paper.pmid == "partial-1")).all():
                session.delete(paper)
            session.commit()


def test_complete_provider_failure_is_controlled_and_creates_no_paper(monkeypatch) -> None:
    from app import literature_pipeline

    investigation_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(Investigation(id=investigation_id, owner_id=_owner_id(), title="Complete failure test", question="What is complete failure handling?", status="SEARCHING", research_plan={"key_concepts": ["CRISPR", "disease"]}))
        session.commit()

    class FailedClient:
        def close(self):
            pass

        def search_pubmed_result(self, query, **kwargs):
            raise LiteratureError("PubMed unavailable.")

        def search_europe_pmc_result(self, query, **kwargs):
            raise LiteratureError("Europe PMC unavailable.")

    monkeypatch.setattr(literature_pipeline, "LiteratureClient", FailedClient)
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            try:
                run_literature_pipeline(session, investigation)
            except LiteraturePipelineError as error:
                assert error.category == "EXTERNAL_PROVIDER_ERROR"
            else:
                raise AssertionError("expected controlled literature failure")
            assert session.scalar(select(Paper).where(Paper.title == "CRISPR therapy for sickle-cell disease")) is None
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
                session.commit()
