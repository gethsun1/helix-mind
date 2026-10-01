"""Provider boundary for C2 provenance anchoring.

The bundled provider is a deterministic local development fixture, never a public anchor.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256


@dataclass(frozen=True)
class AnchorResult:
    provider: str
    anchor_type: str
    external_reference: str
    anchored_at: datetime
    provider_metadata: dict


class ProvenanceAnchorProvider:
    name = "abstract"

    def create_anchor(self, digest: str, asset_version_id: str) -> AnchorResult:
        raise NotImplementedError

    def verify_anchor(self, digest: str, reference: str, metadata: dict) -> dict:
        raise NotImplementedError


class TestLocalAnchorProvider(ProvenanceAnchorProvider):
    name = "test/local"

    @staticmethod
    def reference_for(digest: str, asset_version_id: str) -> str:
        value = sha256(f"test/local:v1:{asset_version_id}:{digest}".encode("utf-8")).hexdigest()
        return f"test-local:v1:{value}"

    def create_anchor(self, digest: str, asset_version_id: str) -> AnchorResult:
        return AnchorResult(self.name, "DETERMINISTIC_LOCAL_REFERENCE", self.reference_for(digest, asset_version_id),
                            datetime.now(timezone.utc), {"provider_scope": "local_test_only", "format": "test-local:v1"})

    def verify_anchor(self, digest: str, reference: str, metadata: dict) -> dict:
        expected = self.reference_for(digest, metadata["asset_version_id"])
        return {"provider_reference_matches": reference == expected, "independent_external_verification": False,
                "verification_scope": "deterministic_local_reference_only"}


def get_anchor_provider() -> ProvenanceAnchorProvider:
    return TestLocalAnchorProvider()
