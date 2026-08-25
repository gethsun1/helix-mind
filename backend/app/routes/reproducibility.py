from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.db import SessionLocal
from app.jobs import start_investigation
from app.models import Investigation, InvestigationEvent, InvestigationRun, ResearchArtifact, ResearchSnapshot, User
from app.queue import get_research_queue
from app.research_reproducibility import compare_snapshots, create_run, digest_json, freeze_snapshot, latest_completed_run
from app.schemas import InvestigationRunRead, InvestigationSnapshotCreate, ResearchArtifactRead, ResearchSnapshotRead
from app.security import get_current_user


router = APIRouter(prefix="/api/v1/investigations", tags=["reproducibility"])


def _scope(session, investigation_id: UUID, user: User) -> Investigation:
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    investigation = session.scalar(query)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return investigation


def _run_read(session, run: InvestigationRun) -> InvestigationRunRead:
    snapshot_id = session.scalar(select(ResearchSnapshot.id).where(ResearchSnapshot.run_id == run.id))
    return InvestigationRunRead(
        id=run.id,
        investigation_id=run.investigation_id,
        parent_run_id=run.parent_run_id,
        run_number=run.run_number,
        status=run.status,
        code_version=run.code_version,
        schema_version=run.schema_version,
        plan_hash=run.plan_hash,
        input_manifest=run.input_manifest,
        provider_metadata=run.provider_metadata,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        snapshot_id=snapshot_id,
    )


def _snapshot_read(snapshot: ResearchSnapshot) -> ResearchSnapshotRead:
    return ResearchSnapshotRead.model_validate(snapshot, from_attributes=True)


@router.get("/{investigation_id}/runs", response_model=list[InvestigationRunRead])
def list_investigation_runs(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[InvestigationRunRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(InvestigationRun).where(InvestigationRun.investigation_id == investigation_id).order_by(InvestigationRun.run_number.desc())).all()
        return [_run_read(session, item) for item in rows]


@router.get("/{investigation_id}/runs/{run_id}", response_model=InvestigationRunRead)
def get_investigation_run(investigation_id: UUID, run_id: UUID, user: User = Depends(get_current_user)) -> InvestigationRunRead:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.id == run_id, InvestigationRun.investigation_id == investigation_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Investigation run not found.")
        return _run_read(session, run)


@router.post("/{investigation_id}/runs", response_model=InvestigationRunRead, status_code=status.HTTP_202_ACCEPTED)
def queue_investigation_rerun(investigation_id: UUID, user: User = Depends(get_current_user)) -> InvestigationRunRead:
    session = SessionLocal()
    try:
        investigation = _scope(session, investigation_id, user)
        if investigation.status.upper() in {"QUEUED", "PLANNING", "SEARCHING", "KNOWLEDGE", "REASONING"}:
            raise HTTPException(status_code=409, detail="Investigation is already queued or running.")
        parent = session.scalar(select(InvestigationRun).where(InvestigationRun.investigation_id == investigation.id).order_by(InvestigationRun.run_number.desc()).limit(1))
        run = create_run(session, investigation, parent_run_id=parent.id if parent else None, status="QUEUED")
        investigation.status = "QUEUED"
        investigation.error_message = None
        investigation.completed_at = None
        session.add(InvestigationEvent(investigation_id=investigation.id, event_type="investigation_rerun_queued", message="A new reproducible investigation run was queued without modifying prior runs.", event_metadata={"run_id": str(run.id), "parent_run_id": str(parent.id) if parent else None, "actor": "admin" if user.role == "ADMIN" else "owner"}))
        session.commit()
        run_id = run.id
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    try:
        get_research_queue().enqueue(start_investigation, str(investigation_id), str(run_id))
    except RedisError as error:
        with SessionLocal() as failed_session:
            failed_run = failed_session.get(InvestigationRun, run_id)
            failed_investigation = failed_session.get(Investigation, investigation_id)
            if failed_run is not None:
                failed_run.status = "FAILED"
                failed_run.error_message = "HelixMind research queue is unavailable."
            if failed_investigation is not None:
                failed_investigation.status = "FAILED"
                failed_investigation.error_message = "HelixMind research queue is unavailable."
            failed_session.commit()
        raise HTTPException(status_code=503, detail="HelixMind research queue is unavailable.") from error
    with SessionLocal() as response_session:
        return _run_read(response_session, response_session.get(InvestigationRun, run_id))


@router.get("/{investigation_id}/snapshots", response_model=list[ResearchSnapshotRead])
def list_investigation_snapshots(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[ResearchSnapshotRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(ResearchSnapshot).where(ResearchSnapshot.investigation_id == investigation_id).order_by(ResearchSnapshot.snapshot_number.desc())).all()
        return [_snapshot_read(item) for item in rows]


@router.post("/{investigation_id}/snapshots", response_model=ResearchSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_investigation_snapshot(investigation_id: UUID, payload: InvestigationSnapshotCreate | None = None, user: User = Depends(get_current_user)) -> ResearchSnapshotRead:
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user)
        requested_run_id = payload.run_id if payload else None
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.id == requested_run_id, InvestigationRun.investigation_id == investigation.id)) if requested_run_id else latest_completed_run(session, investigation.id)
        if requested_run_id and run is None:
            raise HTTPException(status_code=404, detail="Investigation run not found.")
        if run is None:
            if investigation.status.upper() != "COMPLETED":
                raise HTTPException(status_code=409, detail="Only completed investigations can be snapshotted.")
            run = create_run(session, investigation, status="COMPLETED")
            run.started_at = investigation.started_at or investigation.created_at
            run.completed_at = investigation.completed_at or investigation.updated_at
            run.plan_hash = digest_json(investigation.research_plan or {})
            run.provider_metadata = (investigation.research_plan or {}).get("_metadata", {}) if isinstance(investigation.research_plan, dict) else {}
        if run.status != "COMPLETED":
            raise HTTPException(status_code=409, detail="Only completed investigation runs can be snapshotted.")
        try:
            snapshot = freeze_snapshot(session, investigation, run, created_by_user_id=user.id)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _snapshot_read(snapshot)


@router.get("/{investigation_id}/snapshots/compare", response_model=dict)
def compare_investigation_snapshots(investigation_id: UUID, left_snapshot_id: UUID = Query(alias="leftSnapshotId"), right_snapshot_id: UUID = Query(alias="rightSnapshotId"), user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        left = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == left_snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        right = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == right_snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if left is None or right is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        return compare_snapshots(left, right)


@router.get("/{investigation_id}/snapshots/{snapshot_id}", response_model=ResearchSnapshotRead)
def get_investigation_snapshot(investigation_id: UUID, snapshot_id: UUID, user: User = Depends(get_current_user)) -> ResearchSnapshotRead:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        return _snapshot_read(snapshot)


@router.get("/{investigation_id}/snapshots/{snapshot_id}/artifacts", response_model=list[ResearchArtifactRead])
def list_snapshot_artifacts(investigation_id: UUID, snapshot_id: UUID, user: User = Depends(get_current_user)) -> list[ResearchArtifactRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        rows = session.scalars(select(ResearchArtifact).where(ResearchArtifact.snapshot_id == snapshot.id).order_by(ResearchArtifact.created_at.asc())).all()
        return [ResearchArtifactRead(id=item.id, snapshot_id=item.snapshot_id, artifact_type=item.artifact_type, artifact_format=item.artifact_format, status=item.status, generator_version=item.generator_version, schema_version=item.schema_version, content_digest=item.content_digest, manifest_digest=item.manifest_digest, metadata=item.artifact_metadata, created_at=item.created_at) for item in rows]
