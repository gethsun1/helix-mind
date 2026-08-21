from sqlalchemy import select

from app.db import SessionLocal
from app.literature import NormalizedPaper, persist_papers
from app.models import Investigation, InvestigationPaper, Paper, User


def test_investigation_can_be_inserted_and_retrieved() -> None:
    session = SessionLocal()
    try:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        investigation = Investigation(owner_id=owner.id, question="Can CRISPR target HBB for sickle-cell disease?")
        session.add(investigation)
        session.flush()

        stored = session.scalar(select(Investigation).where(Investigation.id == investigation.id))

        assert stored is not None
        assert stored.status == "queued"
        assert stored.question == investigation.question
    finally:
        session.rollback()
        session.close()


def test_literature_papers_are_deduplicated_and_linked_to_an_investigation() -> None:
    session = SessionLocal()
    try:
        owner = session.scalar(select(User).where(User.email == "gethsun09@gmail.com"))
        assert owner is not None
        investigation = Investigation(owner_id=owner.id, question="Can CRISPR target HBB for sickle-cell disease?")
        session.add(investigation)
        session.flush()

        paper = NormalizedPaper(
            source="pubmed",
            external_id="12345",
            title="A real record shape",
            abstract="Abstract from a source.",
            authors=["Researcher A"],
            publication_date=None,
            doi="10.1000/example",
            url="https://pubmed.ncbi.nlm.nih.gov/12345/",
            metadata={"source_records": ["pubmed"]},
        )
        persisted = persist_papers(session, investigation.id, investigation.question, [paper, paper])

        assert len(persisted) == 1
        assert session.scalars(select(Paper).where(Paper.external_id == "12345")).one().title == "A real record shape"
        assert session.scalars(select(InvestigationPaper).where(InvestigationPaper.investigation_id == investigation.id)).one()
    finally:
        session.rollback()
        session.close()
