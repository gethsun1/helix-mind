from sqlalchemy import select

from app.db import SessionLocal
from app.models import Investigation


def test_investigation_can_be_inserted_and_retrieved() -> None:
    session = SessionLocal()
    try:
        investigation = Investigation(question="Can CRISPR target HBB for sickle-cell disease?")
        session.add(investigation)
        session.flush()

        stored = session.scalar(select(Investigation).where(Investigation.id == investigation.id))

        assert stored is not None
        assert stored.status == "queued"
        assert stored.question == investigation.question
    finally:
        session.rollback()
        session.close()
