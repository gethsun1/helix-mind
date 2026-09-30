# C1 — Private Provenance & Rights Foundation

**Status:** Implemented as a private owner-scoped API and database layer. **No public asset directory, chain, wallet, token, marketplace, or license execution is implemented.**

## Architecture and data model

C1 adds a wrapper above existing investigation runs, immutable research snapshots, and generated research artifacts. It does not copy evidence, claims, graph records, semantic extraction, papers, or source text into a second scientific store.

- `ScientificAsset` is a private family record. `created_by_user_id` identifies the HelixMind account that created it and is never used as declared ownership.
- `AssetVersion` binds one family version to one investigation, completed run through its snapshot, snapshot digest, artifact, and artifact digest. Creation validates that the run is completed, the snapshot digest is valid, the artifact belongs to that snapshot, and the artifact carries the same snapshot digest. Source references/digests have no update endpoint; a later research state requires another version in a future versioning operation.
- `AssetRightsDeclaration` stores immutable human-submitted assertions scoped to a version, including an explicitly supplied declared owner, contributors, basis, rights scope, license declaration, third-party material, intended use, and conflict state. Sensitive supporting documents are not stored by this API.
- `AssetEvent` records lifecycle and review events. The API appends events and provides no edit/delete route.

Asset and declaration visibility is constrained to `PRIVATE`. Existing investigation scoping allows the investigation owner and preserves the existing ADMIN exception.

## Eligibility and lifecycle

Version responses include structured deterministic checks for identity, run/snapshot/artifact association, both recorded digests, stored artifact bytes when available, rights declaration completeness, intended use, third-party declaration, private visibility, and unresolved disputes. An unavailable artifact file is reported as a failed byte-integrity check and cannot pass the full eligibility gate.

The lifecycle vocabulary is `DRAFT`, `RESEARCH_ONLY`, `PROVENANCE_READY`, `ASSETIZATION_ELIGIBLE`, `SUPERSEDED`, `REVOKED`, and `WITHDRAWN`. Status changes require a typed append-only event. A review event is a record that a human action occurred; HelixMind does not adjudicate rights. Eligibility is not a scientific quality score or legal opinion.

## Provenance manifest and verification

The private manifest uses schema `asset-manifest-1` and canonicalization `asset-canonical-json-1`. Its SHA-256 is computed independently using the existing canonical JSON helper. It identifies the exact asset/version, investigation, run lineage, snapshot and artifact digests, artifact/generator/schema contract, safe source identifiers, declared rights state, controlled scientific status codes/counts, and contradiction count. Scientific status rejects free-form text to prevent names or other PII entering this export. It excludes publication/evidence text, declared owner/contributor names, private documents, storage keys, and credentials. The snapshot and artifact digest formulas remain unchanged.

Verification reports snapshot digest, artifact record/association, and artifact bytes separately from `scientific_validity: NOT_ASSESSED` and `legal_ownership: NOT_ASSESSED`. Retraction monitoring is not present in the source infrastructure; the manifest explicitly reports `retraction_metadata_available: false` rather than inventing data. Contradiction counts are derived from the frozen snapshot.

A provenance record does not establish legal ownership. An integrity check does not establish scientific truth. A rights declaration is a human assertion, not legal adjudication.

## API and isolation

All endpoints require the existing authenticated-user dependency and scope through `investigation_id` on every request. Asset child records are additionally constrained by both family ID and investigation/version association. There are no public verification or asset routes.

- `POST /api/v1/investigations/{investigation_id}/assets`
- `POST /api/v1/investigations/{investigation_id}/assets/{asset_id}/versions`
- `GET /api/v1/investigations/{investigation_id}/assets`
- `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}`
- `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}/versions/{version_id}`
- `POST /api/v1/investigations/{investigation_id}/assets/{asset_id}/rights-declarations`
- `POST /api/v1/investigations/{investigation_id}/assets/{asset_id}/events`
- `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}/provenance`

The routes are private backend APIs. No dedicated UI was added because the current workstation has no asset management surface; this avoids introducing a second unreviewed representation of rights declarations. The response keeps creator identity, declared ownership, and system verification as distinct fields.

## Security and limitations

Rights declarations are private API data. The export manifest only contains declaration state and contributor count. It does not expose the submitted owner identity, contributor names, private references, or storage credentials. Caller-supplied scientific status is explicitly a declaration/summary and does not replace the snapshot. There is no database trigger preventing privileged direct SQL edits; immutability is enforced by the absence of update/delete API operations, foreign-key restrictions, and append-only application behavior.

Current implementation limitations: declaration revision is additive but review/dispute status changes are audit events rather than legal-status adjudication; artifact byte verification requires the file to exist under the configured private artifact root; retraction metadata is unavailable; there is no asset UI, institutional tenant model, signer credential, external anchor, or legal review workflow. The event endpoint records human review but is not itself restricted to a dedicated reviewer role, consistent with the existing user/admin policy; business authorization policy remains an open decision.

## Testing and migration

Migration `f1a2b3c4d5e6` adds the four asset tables and indexes. Focused backend coverage is in `backend/tests/test_private_assets.py`; the full backend suite and frontend build should be run before acceptance. Browser workflow verification is not applicable because no UI was added.

## C1 deliberately does not implement

No blockchain, smart contract, NFT, token, wallet, marketplace/BASIX integration, public directory, asset trading, payments, license execution, automatic rights verification, ownership inference, legal adjudication, institutional multi-tenancy, M6, M7, or ERN-AI integration.

## C2 prerequisites

C2 remains optional and future. It requires a defined verification use case, public/private disclosure review, manifest and canonicalization test vectors, issuer/key governance and rotation/revocation, privacy and correlation analysis, correction semantics, verifier support, and a decision whether a signed off-chain credential is sufficient. No network or standard is selected by C1.
