from __future__ import annotations

import math
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Investigation, InvestigationPaper, Paper, ResearchSearch, User
from app.schemas import PaperDetailRead, PaperInvestigationRead, PaperPage, PaperRead, ResearchSearchRead
from app.security import get_current_user


router = APIRouter(prefix="/api/v1", tags=["literature"])


def _paper_access_query(paper_id: UUID, user: User):
    query = select(Paper).where(Paper.id == paper_id)
    if user.role != "ADMIN":
        query = query.where(
            Paper.id.in_(
                select(InvestigationPaper.paper_id)
                .join(Investigation, Investigation.id == InvestigationPaper.investigation_id)
                .where(Investigation.owner_id == user.id)
            )
        )
    return query


def _paper_read(paper: Paper, association: InvestigationPaper | None = None) -> PaperRead:
    metadata = paper.paper_metadata if isinstance(paper.paper_metadata, dict) else {}
    source_records = []
    for value in metadata.get("source_records") or [paper.source]:
        normalized = str(value).upper().replace("EUROPEPMC", "EUROPE_PMC")
        if normalized not in source_records:
            source_records.append(normalized)
    return PaperRead(
        id=paper.id,
        source=paper.source,
        external_id=paper.external_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors,
        journal=paper.journal,
        publication_date=paper.publication_date,
        publication_type=paper.publication_type,
        language=paper.language,
        mesh_terms=paper.mesh_terms,
        keywords=paper.keywords,
        doi=paper.doi,
        pmid=paper.pmid,
        pmcid=paper.pmcid,
        url=paper.url,
        metadata=metadata,
        retrieved_at=paper.retrieved_at,
        created_at=paper.created_at,
        updated_at=paper.updated_at,
        source_records=source_records,
        relevance_score=float(association.relevance_score) if association and association.relevance_score is not None else None,
        relevance_reason=association.relevance_reason if association else None,
        source_query=association.source_query if association else None,
        discovered_at=association.discovered_at if association else None,
        selected=association.selected if association else False,
        rank=association.rank if association else None,
    )


def _page(total: int, page: int, page_size: int, items: list[PaperRead]) -> PaperPage:
    return PaperPage(items=items, total=total, page=page, page_size=page_size, page_count=max(1, math.ceil(total / page_size)))


def _paper_page(session: Session, base_query, association_query, page: int, page_size: int, sort: str, source: str | None, year: int | None, query_text: str | None) -> PaperPage:
    if source:
        normalized_source = source.upper().replace("EUROPEPMC", "EUROPE_PMC")
        base_query = base_query.where(or_(Paper.source == normalized_source, Paper.paper_metadata.contains({"source_records": [normalized_source]}), Paper.paper_metadata.contains({"source_records": [normalized_source.lower()]})))
    if year:
        base_query = base_query.where(func.extract("year", Paper.publication_date) == year)
    if query_text:
        term = f"%{query_text.strip()}%"
        base_query = base_query.where(or_(Paper.title.ilike(term), Paper.abstract.ilike(term)))
    total = session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    if sort == "date":
        ordering = [Paper.publication_date.desc().nullslast(), Paper.title.asc()]
    elif sort == "title":
        ordering = [Paper.title.asc()]
    else:
        ordering = [InvestigationPaper.relevance_score.desc().nullslast(), InvestigationPaper.rank.asc().nullslast(), Paper.title.asc()]
    rows = session.execute(association_query.where(Paper.id.in_(base_query.with_only_columns(Paper.id))).order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return _page(total, page, page_size, [_paper_read(paper, association) for paper, association in rows])


@router.get("/investigations/{investigation_id}/papers", response_model=PaperPage)
def investigation_papers(
    investigation_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    source: str | None = None,
    year: int | None = Query(default=None, ge=1900, le=2100),
    sort: str = Query(default="relevance", pattern="^(relevance|date|title)$"),
    user: User = Depends(get_current_user),
) -> PaperPage:
    session = SessionLocal()
    try:
        scope = select(Investigation).where(Investigation.id == investigation_id)
        if user.role != "ADMIN":
            scope = scope.where(Investigation.owner_id == user.id)
        if session.scalar(scope) is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        base = select(Paper.id).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation_id)
        associations = select(Paper, InvestigationPaper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation_id)
        return _paper_page(session, base, associations, page, page_size, sort, source, year, None)
    finally:
        session.close()


@router.get("/investigations/{investigation_id}/searches", response_model=list[ResearchSearchRead])
def investigation_searches(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[ResearchSearchRead]:
    session = SessionLocal()
    try:
        scope = select(Investigation).where(Investigation.id == investigation_id)
        if user.role != "ADMIN":
            scope = scope.where(Investigation.owner_id == user.id)
        if session.scalar(scope) is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        rows = session.scalars(select(ResearchSearch).where(ResearchSearch.investigation_id == investigation_id).order_by(ResearchSearch.executed_at.asc())).all()
        return [ResearchSearchRead.model_validate(row, from_attributes=True) for row in rows]
    finally:
        session.close()


@router.get("/papers/{paper_id}", response_model=PaperDetailRead)
def paper_detail(paper_id: UUID, user: User = Depends(get_current_user)) -> PaperDetailRead:
    session = SessionLocal()
    try:
        paper = session.scalar(_paper_access_query(paper_id, user))
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        association_query = select(InvestigationPaper, Investigation.title).join(Investigation, Investigation.id == InvestigationPaper.investigation_id).where(InvestigationPaper.paper_id == paper_id)
        if user.role != "ADMIN":
            association_query = association_query.where(Investigation.owner_id == user.id)
        associations = session.execute(association_query).all()
        result = _paper_read(paper, associations[0][0] if associations else None)
        return PaperDetailRead(
            **result.model_dump(),
            investigations=[PaperInvestigationRead(id=association.id, title=title, relevance_score=float(association.relevance_score) if association.relevance_score is not None else None, relevance_reason=association.relevance_reason, rank=association.rank, selected=association.selected) for association, title in associations],
        )
    finally:
        session.close()


@router.get("/literature/search", response_model=PaperPage)
def search_literature(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    source: str | None = None,
    year: int | None = Query(default=None, ge=1900, le=2100),
    sort: str = Query(default="relevance", pattern="^(relevance|date|title)$"),
    user: User = Depends(get_current_user),
) -> PaperPage:
    session = SessionLocal()
    try:
        allowed = select(InvestigationPaper.paper_id).join(Investigation, Investigation.id == InvestigationPaper.investigation_id)
        if user.role != "ADMIN":
            allowed = allowed.where(Investigation.owner_id == user.id)
        base = select(Paper.id).where(Paper.id.in_(allowed))
        associations = select(Paper, InvestigationPaper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(Paper.id.in_(allowed))
        return _paper_page(session, base, associations, page, page_size, sort, source, year, q)
    finally:
        session.close()
