import uuid
from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.knowledge import extract_investigation_knowledge
from app.models import Contradiction, Evidence, Hypothesis, Inference, Investigation, InvestigationPaper, KnowledgeGap, Paper, Proposition, User
from app.scientific_reasoning import aggregate_evidence, contradiction_type, evidence_polarity, transitive_support


def _owner_id():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        return owner.id


def test_phase3e_polarity_and_bounded_transitive_rule() -> None:
    assert evidence_polarity("CRISPR targets HBB.") == "SUPPORTS"
    assert evidence_polarity("CRISPR does not target HBB.") == "CONTRADICTS"
    assert evidence_polarity("The results were inconclusive.") == "UNCERTAIN"
    assert transitive_support([("A", "SUPPORTS", "B"), ("B", "SUPPORTS", "C")]) == [("A", "SUPPORTS", "C")]
    direct = Evidence(source_span={"start": 0, "end": 1}, section=None)
    opposing = Evidence(source_span={"start": 0, "end": 1}, section=None)
    assert contradiction_type(direct, opposing) == "DIRECT"
    contextual = Evidence(source_span=None, section="results")
    contextual_opposing = Evidence(source_span=None, section="discussion")
    assert contradiction_type(contextual, contextual_opposing) == "CONTEXTUAL"
    assert contradiction_type(Evidence(source_span=None, section=None), Evidence(source_span=None, section=None)) == "INSUFFICIENT_EVIDENCE"


def test_phase3e_persists_propositions_hypotheses_contradictions_gaps_and_trace() -> None:
    investigation_id = uuid.uuid4()
    paper_ids = [uuid.uuid4(), uuid.uuid4()]
    with SessionLocal() as session:
        session.add(Investigation(id=investigation_id, owner_id=_owner_id(), title="Phase 3E reasoning test", question="What evidence supports or contradicts CRISPR targeting HBB?", status="KNOWLEDGE"))
        session.add_all([
            Paper(id=paper_ids[0], source="PUBMED", external_id="phase3e-positive", title="CRISPR study", abstract="CRISPR targets HBB.", authors=["Author A"], publication_date=date(2024, 1, 1), pmid="phase3e-positive"),
            Paper(id=paper_ids[1], source="EUROPE_PMC", external_id="phase3e-negative", title="CRISPR follow-up", abstract="CRISPR does not target HBB.", authors=["Author B"], publication_date=date(2024, 1, 2), pmid="phase3e-negative"),
        ])
        session.flush()
        session.add_all([InvestigationPaper(investigation_id=investigation_id, paper_id=paper_ids[0], source="PUBMED", source_query="CRISPR HBB"), InvestigationPaper(investigation_id=investigation_id, paper_id=paper_ids[1], source="EUROPE_PMC", source_query="CRISPR HBB")])
        session.commit()

    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            assert investigation is not None
            knowledge = extract_investigation_knowledge(session, investigation)
            assert knowledge["claims"] == 2
            from app.scientific_reasoning import run_scientific_reasoning

            result = run_scientific_reasoning(session, investigation)
            assert result["hypothesis_count"] == 1
            assert result["contradiction_count"] == 1
            assert session.scalar(select(Proposition).where(Proposition.investigation_id == investigation_id)) is not None
            hypothesis = session.scalar(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id))
            assert hypothesis is not None
            assert hypothesis.status == "CONTESTED"
            assert hypothesis.supporting_evidence_count == 1
            assert hypothesis.contradictory_evidence_count == 1
            assert session.scalar(select(Contradiction).where(Contradiction.investigation_id == investigation_id)) is not None
            assert session.scalar(select(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation_id)) is not None
            assert session.scalar(select(Evidence).where(Evidence.investigation_id == investigation_id, Evidence.polarity == "CONTRADICTS")) is not None
            inference = session.scalar(select(Inference).join(Hypothesis, Inference.hypothesis_id == Hypothesis.id).where(Hypothesis.investigation_id == investigation_id))
            assert inference is not None
            assert len(inference.inference_metadata["relationships_applied"]) == 2
    finally:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            if investigation:
                session.delete(investigation)
            for paper_id in paper_ids:
                paper = session.get(Paper, paper_id)
                if paper:
                    session.delete(paper)
            session.commit()
