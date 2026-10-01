import uuid

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.provenance_anchors import TestLocalAnchorProvider
from app.db import SessionLocal
from app.models import AssetEvent, AssetProvenanceAnchor, AssetVersion, ScientificAsset, User
from app.research_reproducibility import digest_json
from app.routes.assets import _manifest
from test_private_assets import _cleanup_assets, _setup_asset
from test_phase4a_reproducibility import TEST_SECRET, _owner_id


def test_local_provider_is_deterministic_and_not_external():
    provider = TestLocalAnchorProvider()
    ref = provider.create_anchor("a" * 64, "version-id")
    check = provider.verify_anchor("a" * 64, ref.external_reference, {"asset_version_id": "version-id"})
    assert ref.external_reference == provider.reference_for("a" * 64, "version-id")
    assert check["provider_reference_matches"] is True
    assert check["independent_external_verification"] is False
    assert ref.provider == "test/local"


def test_anchor_api_binds_version_and_repeated_verification_is_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        created = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "PACKAGE", "title": "C2 fixture", "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
        assert created.status_code == 201, created.text
        asset_id, version_id = created.json()["asset"]["id"], created.json()["version"]["id"]
        client.post(f"/api/v1/investigations/{inv}/assets/{asset_id}/rights-declarations", headers=headers, json={
            "declared_owner": {"type": "declared"}, "ownership_basis": "assertion", "rights_scope": "version",
            "third_party_material": [], "intended_use": "INTERNAL"})
        with SessionLocal() as session:
            session.add(AssetEvent(asset_id=uuid.UUID(asset_id), asset_version_id=uuid.UUID(version_id), actor_id=_owner_id(),
                event_type="RIGHTS_REVIEWED", reason="test readiness", new_status="ASSETIZATION_ELIGIBLE",
                event_metadata={"rights_status": "REVIEWED"}))
            from app.models import ScientificAsset, AssetVersion
            session.get(ScientificAsset, uuid.UUID(asset_id)).status = "ASSETIZATION_ELIGIBLE"
            session.get(AssetVersion, uuid.UUID(version_id)).status = "ASSETIZATION_ELIGIBLE"
            session.commit()
        url = f"/api/v1/investigations/{inv}/assets/{asset_id}/versions/{version_id}/anchors"
        anchor = client.post(url, headers=headers)
        assert anchor.status_code == 201, anchor.text
        body = anchor.json()
        assert body["asset_version_id"] == version_id
        assert body["anchor_provider"] == "test/local"
        assert body["anchor_status"] == "ANCHORED"
        again = client.post(url, headers=headers)
        assert again.json()["id"] == body["id"]
        verify_url = f"{url}/{body['id']}/verify"
        first = client.post(verify_url, headers=headers).json()
        second = client.post(verify_url, headers=headers).json()
        assert first["canonical_digest"] == "verified"
        assert first["external_anchor"] == "locally_reproducible"
        assert first["independent_external_verification"] is False
        assert first["scientific_validity"] == "not_assessed"
        assert first["legal_ownership"] == "not_established"
        assert first["current_digest"] == second["current_digest"]
        assert client.get(url, headers=headers).json()[0]["id"] == body["id"]
        assert client.post(verify_url).status_code == 401
    finally:
        with SessionLocal() as session:
            asset = session.query(ScientificAsset).filter_by(investigation_id=inv).first()
            if asset:
                session.query(AssetProvenanceAnchor).filter_by(scientific_asset_id=asset.id).delete(synchronize_session=False)
                session.commit()
        _cleanup_assets(inv, paper)


def _eligible_fixture(tmp_path, monkeypatch):
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
        "asset_type": "PACKAGE", "title": "C2 coverage", "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
    assert response.status_code == 201, response.text
    asset_id, version_id = response.json()["asset"]["id"], response.json()["version"]["id"]
    rights = client.post(f"/api/v1/investigations/{inv}/assets/{asset_id}/rights-declarations", headers=headers, json={
        "declared_owner": {"type": "declared"}, "ownership_basis": "assertion", "rights_scope": "version",
        "third_party_material": [], "intended_use": "INTERNAL"})
    assert rights.status_code == 201, rights.text
    with SessionLocal() as session:
        session.add(AssetEvent(asset_id=uuid.UUID(asset_id), asset_version_id=uuid.UUID(version_id), actor_id=_owner_id(),
            event_type="RIGHTS_REVIEWED", reason="test readiness", new_status="ASSETIZATION_ELIGIBLE",
            event_metadata={"rights_status": "REVIEWED"}))
        session.get(ScientificAsset, uuid.UUID(asset_id)).status = "ASSETIZATION_ELIGIBLE"
        session.get(AssetVersion, uuid.UUID(version_id)).status = "ASSETIZATION_ELIGIBLE"
        session.commit()
    url = f"/api/v1/investigations/{inv}/assets/{asset_id}/versions/{version_id}/anchors"
    return client, inv, paper, headers, asset_id, version_id, url


def _cleanup_fixture(inv, paper, asset_id):
    with SessionLocal() as session:
        session.query(AssetProvenanceAnchor).filter_by(scientific_asset_id=uuid.UUID(asset_id)).delete(synchronize_session=False)
        session.commit()
    _cleanup_assets(inv, paper)


def test_eligible_gate_exact_digest_and_immutable_version_binding(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        created = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "PACKAGE", "title": "Not ready", "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
        asset_id, version_id = created.json()["asset"]["id"], created.json()["version"]["id"]
        rejected = client.post(f"/api/v1/investigations/{inv}/assets/{asset_id}/versions/{version_id}/anchors", headers=headers)
        assert rejected.status_code == 409
        assert "RIGHTS_DECLARATION" in rejected.json()["detail"]["failed_checks"]
    finally:
        _cleanup_fixture(inv, paper, asset_id)

    client, inv, paper, headers, asset_id, version_id, url = _eligible_fixture(tmp_path, monkeypatch)
    try:
        created = client.post(url, headers=headers)
        assert created.status_code == 201, created.text
        anchor = created.json()
        with SessionLocal() as session:
            asset = session.get(ScientificAsset, uuid.UUID(asset_id))
            version = session.get(AssetVersion, uuid.UUID(version_id))
            stored = session.get(AssetProvenanceAnchor, uuid.UUID(anchor["id"]))
            expected = digest_json(_manifest(session, asset, version))
            assert stored.asset_version_id == uuid.UUID(version_id)
            assert stored.scientific_asset_id == uuid.UUID(asset_id)
            assert stored.canonical_provenance_digest == expected == anchor["canonical_provenance_digest"]
            original_binding = (version.snapshot_id, version.artifact_id, version.version_number)
            stored_digest = stored.canonical_provenance_digest
        assert client.put(url, headers=headers, json={"asset_version_id": str(uuid.uuid4()),
            "canonical_provenance_digest": "0" * 64}).status_code == 405
        assert client.get(url + f"/{anchor['id']}", headers=headers).json()["asset_version_id"] == version_id
        with SessionLocal() as session:
            version = session.get(AssetVersion, uuid.UUID(version_id))
            assert (version.snapshot_id, version.artifact_id, version.version_number) == original_binding
            assert session.get(AssetProvenanceAnchor, uuid.UUID(anchor["id"])).canonical_provenance_digest == stored_digest
        assert client.post(url, headers=headers).json()["id"] == anchor["id"]
    finally:
        _cleanup_fixture(inv, paper, asset_id)


def test_digest_mismatch_is_reported_and_anchor_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    client, inv, paper, headers, asset_id, version_id, url = _eligible_fixture(tmp_path, monkeypatch)
    try:
        anchor = client.post(url, headers=headers).json()
        with SessionLocal() as session:
            session.get(AssetProvenanceAnchor, uuid.UUID(anchor["id"])).canonical_provenance_digest = "0" * 64
            session.commit()
        result = client.post(url + f"/{anchor['id']}/verify", headers=headers)
        assert result.status_code == 200
        assert result.json()["canonical_digest"] == "mismatch"
        assert result.json()["anchor_status"] == "FAILED"
    finally:
        _cleanup_fixture(inv, paper, asset_id)


def test_provider_failure_is_generic_and_secret_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    client, inv, paper, headers, asset_id, version_id, url = _eligible_fixture(tmp_path, monkeypatch)
    class BrokenProvider:
        name = "test/local"
        def create_anchor(self, digest, asset_version_id):
            raise RuntimeError("secret-provider-token-do-not-leak")
    monkeypatch.setattr("app.routes.assets.get_anchor_provider", lambda: BrokenProvider())
    try:
        response = client.post(url, headers=headers)
        assert response.status_code == 503
        assert "secret-provider-token-do-not-leak" not in response.text
        with SessionLocal() as session:
            row = session.query(AssetProvenanceAnchor).filter_by(asset_version_id=uuid.UUID(version_id)).one()
            assert row.anchor_status == "FAILED"
            assert row.error_category == "provider_failure"
            assert "secret-provider-token-do-not-leak" not in str(row.provider_metadata)
    finally:
        _cleanup_fixture(inv, paper, asset_id)


def test_provider_verification_error_is_structured_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    client, inv, paper, headers, asset_id, version_id, url = _eligible_fixture(tmp_path, monkeypatch)
    try:
        anchor = client.post(url, headers=headers).json()
        class BrokenVerifier:
            def verify_anchor(self, digest, reference, metadata):
                raise RuntimeError("secret-verifier-value-do-not-leak")
        monkeypatch.setattr("app.routes.assets.get_anchor_provider", lambda: BrokenVerifier())
        response = client.post(url + f"/{anchor['id']}/verify", headers=headers)
        assert response.status_code == 200
        assert "secret-verifier-value-do-not-leak" not in response.text
        assert response.json()["provider_error_category"] == "provider_failure"
        assert response.json()["anchor_status"] == "FAILED"
    finally:
        _cleanup_fixture(inv, paper, asset_id)


def test_anchor_enforces_owner_investigation_scope_and_rights_separation(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET)
    get_settings.cache_clear()
    client, inv, paper, headers, asset_id, version_id, url = _eligible_fixture(tmp_path, monkeypatch)
    outsider_id = None
    try:
        anchor = client.post(url, headers=headers).json()
        with SessionLocal() as session:
            outsider = User(email=f"c2-outsider-{uuid.uuid4()}@example.invalid", role="USER")
            session.add(outsider); session.commit(); outsider_id = outsider.id
        outsider_headers = {"Authorization": f"Bearer {jwt.encode({'sub': str(outsider_id)}, TEST_SECRET, algorithm='HS256')}"}
        assert client.get(url, headers=outsider_headers).status_code == 404
        assert client.post(url + f"/{anchor['id']}/verify", headers=outsider_headers).status_code == 404
        other_investigation = uuid.uuid4()
        assert client.get(f"/api/v1/investigations/{other_investigation}/assets/{asset_id}/versions/{version_id}/anchors", headers=headers).status_code == 404
        result = client.post(url + f"/{anchor['id']}/verify", headers=headers).json()
        assert result["rights"] == "declared_separately"
        assert result["scientific_validity"] == "not_assessed"
        assert result["legal_ownership"] == "not_established"
        with SessionLocal() as session:
            version = session.get(AssetVersion, uuid.UUID(version_id))
            assert session.query(AssetProvenanceAnchor).filter_by(asset_version_id=version.id).count() == 1
    finally:
        if outsider_id:
            with SessionLocal() as session:
                outsider = session.get(User, outsider_id)
                if outsider: session.delete(outsider); session.commit()
        _cleanup_fixture(inv, paper, asset_id)
