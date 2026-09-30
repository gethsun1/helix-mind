"""Private scientific asset provenance and human rights declarations."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (AssetEvent, AssetRightsDeclaration, AssetVersion, Investigation,
                        InvestigationRun, ResearchArtifact, ResearchSnapshot, ScientificAsset, User, AssetProvenanceAnchor)
from app.research_reproducibility import digest_json
from app.provenance_anchors import get_anchor_provider
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/investigations/{investigation_id}/assets", tags=["private-assets"])
ASSET_SCHEMA = "asset-manifest-1"
ASSET_CANONICALIZATION = "asset-canonical-json-1"
LIFECYCLE = {"DRAFT", "RESEARCH_ONLY", "PROVENANCE_READY", "ASSETIZATION_ELIGIBLE", "SUPERSEDED", "REVOKED", "WITHDRAWN"}
EVENTS = {"CORRECTION", "SUPERSEDED", "REVOKED", "WITHDRAWN", "RIGHTS_REVIEWED", "RIGHTS_DISPUTED"}


class ScientificStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["PROVISIONAL", "SUPPORTED", "CONTESTED", "UNKNOWN"] = "UNKNOWN"
    uncertainty_level: Literal["LOW", "MODERATE", "HIGH", "UNKNOWN"] = "UNKNOWN"
    supporting_evidence_count: int | None = Field(default=None, ge=0)
    contradictory_evidence_count: int | None = Field(default=None, ge=0)
    source_retraction_state: Literal["UNKNOWN", "CHECKED_NO_RETRACTIONS", "RETRACTIONS_PRESENT"] = "UNKNOWN"
    as_of: str | None = Field(default=None, max_length=32)


class CreateAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    snapshot_id: UUID
    artifact_id: UUID
    visibility: Literal["PRIVATE"] = "PRIVATE"
    status: Literal["DRAFT", "RESEARCH_ONLY"] = "DRAFT"
    scientific_status: ScientificStatus = Field(default_factory=ScientificStatus)


class RightsDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    declared_owner: dict[str, Any]
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    ownership_basis: str = Field(min_length=1, max_length=4000)
    rights_scope: str = Field(min_length=1, max_length=4000)
    license_declaration: dict[str, Any] = Field(default_factory=dict)
    third_party_material: list[dict[str, Any]]
    intended_use: str = Field(min_length=1, max_length=64)
    visibility: Literal["PRIVATE"] = "PRIVATE"
    conflict_status: Literal["NONE_DECLARED", "UNRESOLVED"] = "NONE_DECLARED"
    reason: str | None = Field(default=None, max_length=4000)


class CreateAssetVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: UUID
    artifact_id: UUID
    scientific_status: ScientificStatus = Field(default_factory=ScientificStatus)


class AssetEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str
    reason: str = Field(min_length=1, max_length=4000)
    new_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _scope(session, investigation_id: UUID, user: User) -> Investigation:
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    obj = session.scalar(query)
    if obj is None:
        raise HTTPException(404, "Investigation not found.")
    return obj


def _asset(session, investigation_id: UUID, asset_id: UUID) -> ScientificAsset:
    obj = session.scalar(select(ScientificAsset).where(ScientificAsset.id == asset_id, ScientificAsset.investigation_id == investigation_id))
    if obj is None:
        raise HTTPException(404, "Asset not found.")
    return obj


def _content_digest(artifact: ResearchArtifact) -> tuple[bool | None, str | None]:
    if not artifact.storage_key:
        return None, "Artifact bytes are unavailable in private storage."
    root = Path(get_settings().artifact_root).resolve()
    path = (root / artifact.storage_key).resolve()
    if root not in path.parents or not path.is_file():
        return None, "Artifact bytes are unavailable in private storage."
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    return actual == artifact.content_digest, None if actual == artifact.content_digest else "Stored artifact bytes do not match the recorded digest."


def _rights_status(session, asset: ScientificAsset, version: AssetVersion, declaration: AssetRightsDeclaration | None) -> str:
    if declaration is None:
        return "UNDECLARED"
    events = session.scalars(select(AssetEvent).where(AssetEvent.asset_version_id == version.id).order_by(AssetEvent.timestamp, AssetEvent.id)).all()
    current = declaration.rights_status
    for event in events:
        if event.event_type == "RIGHTS_REVIEWED": current = "REVIEWED"
        elif event.event_type == "RIGHTS_DISPUTED": current = "DISPUTED"
        elif event.event_type == "REVOKED": current = "REVOKED"
    return current


def _conflict_status(session, version: AssetVersion, declaration: AssetRightsDeclaration | None) -> str:
    if declaration is None:
        return "UNKNOWN"
    events = session.scalars(select(AssetEvent).where(AssetEvent.asset_version_id == version.id).order_by(AssetEvent.timestamp, AssetEvent.id)).all()
    current = declaration.conflict_status
    for event in events:
        if event.event_type == "RIGHTS_DISPUTED": current = "UNRESOLVED"
        elif event.event_type == "RIGHTS_REVIEWED" and event.event_metadata.get("conflict_resolved") is True: current = "NONE_DECLARED"
    return current


def _checks(session, asset: ScientificAsset, version: AssetVersion) -> list[dict[str, Any]]:
    snapshot = session.get(ResearchSnapshot, version.snapshot_id)
    artifact = session.get(ResearchArtifact, version.artifact_id)
    run = session.get(InvestigationRun, snapshot.run_id) if snapshot else None
    bytes_valid, bytes_message = _content_digest(artifact) if artifact else (False, "Artifact record is missing.")
    rights = session.scalar(select(AssetRightsDeclaration).where(AssetRightsDeclaration.asset_version_id == version.id).order_by(AssetRightsDeclaration.declared_at.desc()).limit(1))
    checks = [
        ("ASSET_IDENTITY", bool(asset.id and version.id), "Stable asset and version identities exist."),
        ("RUN_COMPLETED", bool(run and run.status == "COMPLETED"), "Source run is completed."),
        ("SNAPSHOT_SCOPE", bool(snapshot and snapshot.investigation_id == asset.investigation_id == version.investigation_id), "Snapshot belongs to this investigation."),
        ("SNAPSHOT_DIGEST", bool(snapshot and digest_json(snapshot.manifest) == snapshot.manifest_digest == version.snapshot_manifest_digest), "Snapshot manifest digest matches."),
        ("ARTIFACT_COMPLETED", bool(artifact and artifact.status == "COMPLETED" and artifact.content_digest), "Artifact is completed and has a content digest."),
        ("ARTIFACT_SCOPE", bool(artifact and snapshot and artifact.snapshot_id == snapshot.id), "Artifact is bound to the selected snapshot."),
        ("ARTIFACT_MANIFEST", bool(artifact and snapshot and artifact.manifest_digest == snapshot.manifest_digest), "Artifact records the selected snapshot digest."),
        ("ARTIFACT_BYTES", bytes_valid is True, "Artifact bytes match their recorded digest." if bytes_valid is True else (bytes_message or "Artifact bytes could not be verified.")),
        ("PROVENANCE_REFERENCES", bool(snapshot and run and artifact and artifact.content_digest), "Run, snapshot, and artifact references are complete."),
        ("RIGHTS_DECLARATION", bool(rights and rights.declared_owner), "An explicit declared owner is present."),
        ("RIGHTS_STATUS", bool(rights and _rights_status(session, asset, version, rights) in {"DECLARED", "DOCUMENTED", "REVIEWED"}), "Rights declaration has a usable declared status."),
        ("THIRD_PARTY_DECLARED", bool(rights and rights.third_party_material is not None), "Third-party material status is declared."),
        ("INTENDED_USE", bool(rights and rights.intended_use), "Intended use is declared."),
        ("PRIVATE_VISIBILITY", asset.visibility == "PRIVATE" and (not rights or rights.visibility == "PRIVATE"), "Asset and declaration are private."),
        ("NO_UNRESOLVED_DISPUTE", bool(not rights or _conflict_status(session, version, rights) != "UNRESOLVED"), "No unresolved blocking dispute is recorded."),
    ]
    return [{"code": code, "passed": bool(passed), "message": message} for code, passed, message in checks]


def _manifest(session, asset: ScientificAsset, version: AssetVersion) -> dict[str, Any]:
    snapshot = session.get(ResearchSnapshot, version.snapshot_id)
    artifact = session.get(ResearchArtifact, version.artifact_id)
    run = session.get(InvestigationRun, snapshot.run_id) if snapshot else None
    rights = session.scalar(select(AssetRightsDeclaration).where(AssetRightsDeclaration.asset_version_id == version.id).order_by(AssetRightsDeclaration.declared_at.desc()).limit(1))
    manifest = {
        "schema_version": ASSET_SCHEMA, "canonicalization_version": ASSET_CANONICALIZATION,
        "asset_id": str(asset.id), "asset_version_id": str(version.id), "version_number": version.version_number,
        "investigation_id": str(asset.investigation_id), "source_run_id": str(run.id) if run else None,
        "run_number": run.run_number if run else None, "parent_run_id": str(run.parent_run_id) if run and run.parent_run_id else None,
        "snapshot_id": str(snapshot.id) if snapshot else None, "snapshot_manifest_digest": version.snapshot_manifest_digest,
        "artifact_id": str(artifact.id) if artifact else None, "artifact_content_digest": version.artifact_content_digest,
        "artifact_type": artifact.artifact_type if artifact else None, "artifact_format": artifact.artifact_format if artifact else None,
        "generator_version": artifact.generator_version if artifact else None, "artifact_schema_version": artifact.schema_version if artifact else None,
        "source_references": [{k: p.get(k) for k in ("source", "external_id", "doi", "pmid", "pmcid")} for p in (snapshot.manifest.get("papers", []) if snapshot else [])],
        "rights_status": _rights_status(session, asset, version, rights), "conflict_status": _conflict_status(session, version, rights),
        "contributor_count": len(rights.contributors) if rights else 0,
        "scientific_status": version.scientific_status,
        "contradiction_count": len(snapshot.manifest.get("contradictions", [])) if snapshot else None,
        "uncertainty_available": any("uncertainty" in x for x in snapshot.manifest.get("hypotheses", [])) if snapshot else None,
        "retraction_metadata_available": False,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
    return manifest


def _version_read(session, asset: ScientificAsset, version: AssetVersion) -> dict[str, Any]:
    checks = _checks(session, asset, version)
    return {"id": version.id, "asset_id": asset.id, "version_number": version.version_number, "parent_version_id": version.parent_version_id,
            "snapshot_id": version.snapshot_id, "artifact_id": version.artifact_id, "snapshot_manifest_digest": version.snapshot_manifest_digest,
            "artifact_content_digest": version.artifact_content_digest, "schema_version": version.schema_version,
            "canonicalization_version": version.canonicalization_version, "status": version.status, "created_at": version.created_at,
            "eligibility": {"eligible": all(c["passed"] for c in checks), "checks": checks}}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_asset(investigation_id: UUID, payload: CreateAsset, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user)
        if investigation.status != "COMPLETED":
            raise HTTPException(409, "Assets require a completed investigation.")
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == payload.snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if snapshot is None:
            raise HTTPException(422, "Snapshot does not belong to this investigation.")
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.id == snapshot.run_id, InvestigationRun.investigation_id == investigation_id))
        if run is None or run.status != "COMPLETED":
            raise HTTPException(422, "A completed source run is required.")
        if digest_json(snapshot.manifest) != snapshot.manifest_digest:
            raise HTTPException(422, "Snapshot manifest digest is invalid.")
        artifact = session.scalar(select(ResearchArtifact).where(ResearchArtifact.id == payload.artifact_id, ResearchArtifact.snapshot_id == snapshot.id))
        if artifact is None:
            raise HTTPException(422, "Artifact does not belong to the selected snapshot.")
        if artifact.status != "COMPLETED" or not artifact.content_digest or artifact.manifest_digest != snapshot.manifest_digest:
            raise HTTPException(422, "A completed artifact with matching snapshot digest is required.")
        bytes_valid, msg = _content_digest(artifact)
        if bytes_valid is False:
            raise HTTPException(422, msg)
        asset = ScientificAsset(investigation_id=investigation.id, created_by_user_id=user.id, asset_type=payload.asset_type,
                                title=payload.title, visibility="PRIVATE", status=payload.status)
        session.add(asset)
        session.flush()
        version = AssetVersion(asset_id=asset.id, version_number=1, investigation_id=investigation.id,
                                snapshot_id=snapshot.id, artifact_id=artifact.id, snapshot_manifest_digest=snapshot.manifest_digest,
                                artifact_content_digest=artifact.content_digest, scientific_status=payload.scientific_status.model_dump(),
                                status=payload.status)
        session.add(version)
        session.flush()
        session.add_all([AssetEvent(asset_id=asset.id, asset_version_id=version.id, actor_id=user.id, event_type="CREATED", new_status=payload.status, event_metadata={}),
                         AssetEvent(asset_id=asset.id, asset_version_id=version.id, actor_id=user.id, event_type="VERSION_CREATED", new_status=payload.status, event_metadata={"version_number": 1})])
        session.commit()
        session.refresh(asset); session.refresh(version)
        return {"asset": asset, "version": _version_read(session, asset, version)}


@router.get("")
def list_assets(investigation_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        assets = session.scalars(select(ScientificAsset).where(ScientificAsset.investigation_id == investigation_id).order_by(ScientificAsset.created_at.desc())).all()
        return [{"id": a.id, "investigation_id": a.investigation_id, "title": a.title, "asset_type": a.asset_type, "visibility": a.visibility, "status": a.status,
                 "created_by_user_id": a.created_by_user_id, "created_at": a.created_at,
                 "versions": [_version_read(session, a, v) for v in session.scalars(select(AssetVersion).where(AssetVersion.asset_id == a.id).order_by(AssetVersion.version_number.desc())).all()]} for a in assets]


@router.get("/{asset_id}")
def get_asset(investigation_id: UUID, asset_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        versions = session.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc())).all()
        events = session.scalars(select(AssetEvent).where(AssetEvent.asset_id == asset.id).order_by(AssetEvent.timestamp, AssetEvent.id)).all()
        rights = session.scalars(select(AssetRightsDeclaration).where(AssetRightsDeclaration.asset_version_id.in_([v.id for v in versions])).order_by(AssetRightsDeclaration.declared_at)).all() if versions else []
        return {"asset": asset, "versions": [_version_read(session, asset, v) for v in versions], "rights_declarations": rights,
                "events": [{"id": e.id, "event_type": e.event_type, "actor_id": e.actor_id, "reason": e.reason, "previous_status": e.previous_status, "new_status": e.new_status, "metadata": e.event_metadata, "timestamp": e.timestamp} for e in events]}


@router.get("/{asset_id}/versions/{version_id}")
def get_version(investigation_id: UUID, asset_id: UUID, version_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        version = session.scalar(select(AssetVersion).where(AssetVersion.id == version_id, AssetVersion.asset_id == asset.id, AssetVersion.investigation_id == investigation_id))
        if version is None: raise HTTPException(404, "Asset version not found.")
        return _version_read(session, asset, version)


@router.post("/{asset_id}/versions", status_code=201)
def create_asset_version(investigation_id: UUID, asset_id: UUID, payload: CreateAssetVersion, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        if investigation.status != "COMPLETED": raise HTTPException(409, "A completed investigation is required.")
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == payload.snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if snapshot is None or digest_json(snapshot.manifest) != snapshot.manifest_digest:
            raise HTTPException(422, "A valid snapshot from this investigation is required.")
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.id == snapshot.run_id, InvestigationRun.investigation_id == investigation_id))
        artifact = session.scalar(select(ResearchArtifact).where(ResearchArtifact.id == payload.artifact_id, ResearchArtifact.snapshot_id == snapshot.id))
        if run is None or run.status != "COMPLETED": raise HTTPException(422, "A completed source run is required.")
        if artifact is None or artifact.status != "COMPLETED" or not artifact.content_digest or artifact.manifest_digest != snapshot.manifest_digest:
            raise HTTPException(422, "A completed artifact belonging to this snapshot is required.")
        bytes_valid, message = _content_digest(artifact)
        if bytes_valid is False: raise HTTPException(422, message)
        previous = session.scalar(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc()).limit(1))
        number = (previous.version_number if previous else 0) + 1
        version = AssetVersion(asset_id=asset.id, version_number=number, parent_version_id=previous.id if previous else None,
            investigation_id=investigation_id, snapshot_id=snapshot.id, artifact_id=artifact.id,
            snapshot_manifest_digest=snapshot.manifest_digest, artifact_content_digest=artifact.content_digest,
            scientific_status=payload.scientific_status.model_dump(), status="DRAFT")
        session.add(version); session.flush()
        session.add(AssetEvent(asset_id=asset.id, asset_version_id=version.id, actor_id=user.id,
            event_type="VERSION_CREATED", previous_status=previous.status if previous else None, new_status="DRAFT",
            event_metadata={"version_number": number, "parent_version_id": str(previous.id) if previous else None}))
        session.commit(); session.refresh(version)
        return _version_read(session, asset, version)


@router.post("/{asset_id}/rights-declarations", status_code=201)
def declare_rights(investigation_id: UUID, asset_id: UUID, payload: RightsDeclaration, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        version = session.scalar(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc()).limit(1))
        if version is None: raise HTTPException(404, "Asset version not found.")
        declaration = AssetRightsDeclaration(asset_version_id=version.id, declaration_actor_id=user.id,
            declared_owner=payload.declared_owner, contributors=payload.contributors, ownership_basis=payload.ownership_basis,
            rights_scope=payload.rights_scope, license_declaration=payload.license_declaration, third_party_material=payload.third_party_material,
            intended_use=payload.intended_use, visibility="PRIVATE", rights_status="DECLARED", conflict_status=payload.conflict_status, reason=payload.reason)
        session.add(declaration); session.flush()
        session.add(AssetEvent(asset_id=asset.id, asset_version_id=version.id, actor_id=user.id, event_type="RIGHTS_DECLARED", reason=payload.reason,
                               event_metadata={"declaration_id": str(declaration.id), "rights_status": "DECLARED"}))
        session.commit(); session.refresh(declaration)
        return {"id": declaration.id, "asset_version_id": declaration.asset_version_id, "declaration_actor_id": declaration.declaration_actor_id,
                "declared_owner": declaration.declared_owner, "rights_status": declaration.rights_status, "conflict_status": declaration.conflict_status, "declared_at": declaration.declared_at}


@router.post("/{asset_id}/events", status_code=201)
def add_asset_event(investigation_id: UUID, asset_id: UUID, payload: AssetEventInput, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        if payload.event_type not in EVENTS: raise HTTPException(422, "Unsupported asset event type.")
        version = session.scalar(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc()).limit(1))
        implied_status = {"SUPERSEDED": "SUPERSEDED", "REVOKED": "REVOKED", "WITHDRAWN": "WITHDRAWN", "RIGHTS_DISPUTED": "RESEARCH_ONLY"}.get(payload.event_type)
        target = implied_status or payload.new_status
        if target is not None and target not in LIFECYCLE: raise HTTPException(422, "Unsupported lifecycle status.")
        if payload.event_type == "RIGHTS_REVIEWED" and target not in {None, "PROVENANCE_READY", "ASSETIZATION_ELIGIBLE"}:
            raise HTTPException(422, "Rights review can only record provenance readiness or eligibility.")
        if payload.event_type == "RIGHTS_REVIEWED" and version is None:
            raise HTTPException(409, "An asset version is required for rights review.")
        if target in {"PROVENANCE_READY", "ASSETIZATION_ELIGIBLE"}:
            checks = _checks(session, asset, version) if version else []
            required = checks if target == "ASSETIZATION_ELIGIBLE" else [c for c in checks if c["code"] in {"RUN_COMPLETED", "SNAPSHOT_SCOPE", "SNAPSHOT_DIGEST", "ARTIFACT_COMPLETED", "ARTIFACT_SCOPE", "ARTIFACT_MANIFEST", "ARTIFACT_BYTES", "PROVENANCE_REFERENCES", "PRIVATE_VISIBILITY"}]
            failed = [c["code"] for c in required if not c["passed"]]
            if failed: raise HTTPException(409, {"message": "Lifecycle transition checks failed.", "failed_checks": failed})
        previous = asset.status
        if target:
            asset.status = target
            if version: version.status = target
        event = AssetEvent(asset_id=asset.id, asset_version_id=version.id if version else None, actor_id=user.id,
                           event_type=payload.event_type, reason=payload.reason, previous_status=previous, new_status=target, event_metadata=payload.metadata)
        if payload.event_type == "RIGHTS_REVIEWED": event.event_metadata = {**payload.metadata, "rights_status": "REVIEWED"}
        elif payload.event_type == "RIGHTS_DISPUTED": event.event_metadata = {**payload.metadata, "rights_status": "DISPUTED"}
        elif payload.event_type == "REVOKED": event.event_metadata = {**payload.metadata, "rights_status": "REVOKED"}
        session.add(event); session.commit(); session.refresh(event)
        return event


@router.get("/{asset_id}/provenance")
def asset_provenance(investigation_id: UUID, asset_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user); asset = _asset(session, investigation_id, asset_id)
        version = session.scalar(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc()).limit(1))
        if version is None: raise HTTPException(404, "Asset version not found.")
        manifest = _manifest(session, asset, version)
        checks = _checks(session, asset, version)
        return {"manifest": manifest, "manifest_digest": digest_json(manifest), "canonicalization_version": ASSET_CANONICALIZATION,
                "verification": {"integrity_verified": all(c["passed"] for c in checks if c["code"] not in {"RIGHTS_DECLARATION", "RIGHTS_STATUS", "THIRD_PARTY_DECLARED", "INTENDED_USE", "PRIVATE_VISIBILITY", "NO_UNRESOLVED_DISPUTE"}),
                                 "checks": checks, "scientific_validity": "NOT_ASSESSED", "legal_ownership": "NOT_ASSESSED"}}


def _anchor_read(row: AssetProvenanceAnchor) -> dict[str, Any]:
    return {"id": row.id, "scientific_asset_id": row.scientific_asset_id, "asset_version_id": row.asset_version_id,
            "canonical_provenance_digest": row.canonical_provenance_digest, "anchor_provider": row.anchor_provider,
            "anchor_type": row.anchor_type, "external_reference": row.external_reference, "anchor_status": row.anchor_status,
            "requested_at": row.requested_at, "anchored_at": row.anchored_at, "provider_metadata": row.provider_metadata,
            "error_category": row.error_category}


def _resolve_version(session, investigation_id: UUID, asset_id: UUID, version_id: UUID, user: User):
    _scope(session, investigation_id, user)
    asset = _asset(session, investigation_id, asset_id)
    version = session.scalar(select(AssetVersion).where(AssetVersion.id == version_id,
        AssetVersion.asset_id == asset.id, AssetVersion.investigation_id == investigation_id))
    if version is None:
        raise HTTPException(404, "Asset version not found.")
    return asset, version


@router.post("/{asset_id}/versions/{version_id}/anchors", status_code=201)
def create_anchor(investigation_id: UUID, asset_id: UUID, version_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        asset, version = _resolve_version(session, investigation_id, asset_id, version_id, user)
        checks = _checks(session, asset, version)
        failed = [check["code"] for check in checks if not check["passed"]]
        if failed:
            raise HTTPException(409, {"message": "Asset version is not eligible for anchoring.", "failed_checks": failed})
        manifest = _manifest(session, asset, version)
        digest = digest_json(manifest)
        existing = session.scalar(select(AssetProvenanceAnchor).where(
            AssetProvenanceAnchor.asset_version_id == version.id,
            AssetProvenanceAnchor.canonical_provenance_digest == digest,
            AssetProvenanceAnchor.anchor_provider == "test/local"))
        if existing:
            return _anchor_read(existing)
        provider = get_anchor_provider()
        try:
            result = provider.create_anchor(digest, str(version.id))
        except Exception as error:
            category = "timeout" if isinstance(error, TimeoutError) else "provider_failure"
            row = AssetProvenanceAnchor(scientific_asset_id=asset.id, asset_version_id=version.id,
                canonical_provenance_digest=digest, anchor_provider=provider.name, anchor_type="DETERMINISTIC_LOCAL_REFERENCE",
                external_reference="", anchor_status="FAILED", created_by_user_id=user.id, error_category=category,
                provider_metadata={"provider_scope": "local_test_only"})
            session.add(row); session.commit()
            raise HTTPException(503, "Anchor provider timed out." if category == "timeout" else "Anchor provider failed.") from None
        row = AssetProvenanceAnchor(scientific_asset_id=asset.id, asset_version_id=version.id,
            canonical_provenance_digest=digest, anchor_provider=result.provider, anchor_type=result.anchor_type,
            external_reference=result.external_reference, anchor_status="ANCHORED", anchored_at=result.anchored_at,
            created_by_user_id=user.id, provider_metadata=result.provider_metadata,
            verification_metadata={"asset_version_id": str(version.id)})
        session.add(row); session.commit(); session.refresh(row)
        return _anchor_read(row)


@router.get("/{asset_id}/versions/{version_id}/anchors")
def list_anchors(investigation_id: UUID, asset_id: UUID, version_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _, version = _resolve_version(session, investigation_id, asset_id, version_id, user)
        rows = session.scalars(select(AssetProvenanceAnchor).where(AssetProvenanceAnchor.asset_version_id == version.id)
                               .order_by(AssetProvenanceAnchor.created_at)).all()
        return [_anchor_read(row) for row in rows]


@router.get("/{asset_id}/versions/{version_id}/anchors/{anchor_id}")
def get_anchor(investigation_id: UUID, asset_id: UUID, version_id: UUID, anchor_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _, version = _resolve_version(session, investigation_id, asset_id, version_id, user)
        row = session.scalar(select(AssetProvenanceAnchor).where(AssetProvenanceAnchor.id == anchor_id,
            AssetProvenanceAnchor.asset_version_id == version.id))
        if row is None: raise HTTPException(404, "Anchor not found.")
        return _anchor_read(row)


@router.post("/{asset_id}/versions/{version_id}/anchors/{anchor_id}/verify")
def verify_anchor(investigation_id: UUID, asset_id: UUID, version_id: UUID, anchor_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        asset, version = _resolve_version(session, investigation_id, asset_id, version_id, user)
        row = session.scalar(select(AssetProvenanceAnchor).where(AssetProvenanceAnchor.id == anchor_id,
            AssetProvenanceAnchor.asset_version_id == version.id))
        if row is None: raise HTTPException(404, "Anchor not found.")
        snapshot = session.get(ResearchSnapshot, version.snapshot_id)
        snapshot_valid = bool(snapshot and digest_json(snapshot.manifest) == snapshot.manifest_digest == version.snapshot_manifest_digest)
        current_digest = digest_json(_manifest(session, asset, version))
        digest_matches = current_digest == row.canonical_provenance_digest
        artifact = session.get(ResearchArtifact, version.artifact_id)
        bytes_valid, bytes_note = _content_digest(artifact) if artifact else (False, "Artifact record is missing.")
        provider_error = None
        if row.anchor_provider == "test/local":
            try:
                provider_result = get_anchor_provider().verify_anchor(row.canonical_provenance_digest,
                    row.external_reference, row.verification_metadata)
            except Exception as error:
                provider_error = "timeout" if isinstance(error, TimeoutError) else "provider_failure"
                provider_result = {"provider_reference_matches": False, "independent_external_verification": False,
                    "verification_scope": "provider_error"}
        else:
            provider_result = {"provider_reference_matches": False, "independent_external_verification": False,
                "verification_scope": "provider_unavailable"}
        row.error_category = provider_error
        row.anchor_status = "VERIFIED" if digest_matches and provider_result["provider_reference_matches"] else "FAILED"
        session.commit()
        return {"anchor_id": str(row.id), "asset_version_exists": True,
            "asset_version_immutability": "version_record_present", "snapshot_integrity": "verified" if snapshot_valid else "failed",
            "canonical_digest": "verified" if digest_matches else "mismatch", "anchored_digest": row.canonical_provenance_digest,
            "current_digest": current_digest, "artifact_bytes": "verified" if bytes_valid is True else "unavailable" if bytes_valid is None else "mismatch",
            "artifact_note": bytes_note, "external_anchor": "locally_reproducible" if provider_result["provider_reference_matches"] else "failed",
            "provider_error_category": provider_error,
            "independent_external_verification": provider_result["independent_external_verification"],
            "anchor_status": row.anchor_status, "provider": row.anchor_provider,
            "scientific_validity": "not_assessed", "legal_ownership": "not_established",
            "licensing_authority": "not_established", "rights": "declared_separately"}
