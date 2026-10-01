# C2 — External Provenance Anchor

## Objective and relationship to C1

C2 associates an eligible immutable `AssetVersion` with a provider reference for the SHA-256 digest of its C1 private provenance manifest. C1 continues to own asset eligibility, rights declarations, artifact-byte checks, and manifest construction. C2 adds no second digest scheme. The manifest is canonicalized by C1 `canonical_json` (sorted keys, compact JSON, UTF-8) and hashed by `digest_json` (SHA-256).

## Mechanism selected

This repository has no configured production timestamp, signature, ledger, or content-addressed provider. C2 therefore ships a provider interface and a deterministic `TestLocalAnchorProvider`. Its reference is derived from provider/version labels, AssetVersion UUID, and canonical digest. It is a local reproducibility fixture, not a public external proof. It does not establish existence outside HelixMind or time outside HelixMind and is not independently verifiable outside this implementation. `anchored_at` is local record time only.

The production boundary is `ProvenanceAnchorProvider.create_anchor` / `verify_anchor`. A production provider must obtain and independently verify a real attestation before being configured. Provider credentials must come from secret configuration and must never be persisted or returned. Any future choice must document privacy, cost, availability, failure, verification, and operating requirements before use.

## Lifecycle and persistence

`AssetProvenanceAnchor` binds one asset ID, one immutable AssetVersion ID, one canonical digest, provider/type, external reference, status, times, safe metadata, and creator. The database uniqueness constraint prevents duplicate records for the same version/digest/provider. A different AssetVersion or changed canonical digest requires a distinct anchor record. The table uses restrictive foreign keys and is private behind investigation-scoped APIs.

The local provider returns `ANCHORED`; verification can advance the row to `VERIFIED` or `FAILED`. Provider failures are categorized without exception or secret text. A production implementation may introduce asynchronous `REQUESTED`/`PENDING` transitions when its operating model requires them.

## Verification semantics

Verification recomputes the current C1 asset provenance manifest digest, checks the snapshot manifest digest, compares the current digest with the recorded anchored digest, checks the local reference derivation, and reports artifact-byte state independently. Missing artifact bytes do not invalidate an otherwise matching manifest digest. The response explicitly returns scientific validity `not_assessed`, legal ownership and licensing authority `not_established`, and rights `declared_separately`. The local provider always reports `independent_external_verification: false`.

The immutable version row is treated as the binding identity; C2 does not update or reassign it. Any canonical manifest changes produce a digest mismatch. SHA-256 integrity does not establish scientific validity, authorship, title, licensing authority, originality, regulatory approval, efficacy, or commercial rights.

## Privacy and security

All routes require existing bearer authentication and investigation ownership (including the existing ADMIN access rule). Cross-owner/investigation lookups return the existing not-found semantics. No public verification route is added. Records contain only IDs, digest, provider reference, state, and safe provider metadata; research content and rights declaration bodies are not exported by C2 APIs. No provider secret is stored.

## Failure modes and limitations

The local provider cannot attest to independent existence or time. Database loss or modification can affect its reference record. A future remote provider may timeout, be unavailable, reject a request, or later be unable to verify its reference; those outcomes must remain explicit and must not change scientific or rights assertions. No production provider, credentials, public route, or external operational dependency is configured.

## Non-goals and unresolved decisions

C2 is not NFT minting, tokenization, marketplace or BASIX integration, automated licensing, or legal ownership verification. Selecting and operating a production timestamp/attestation/ledger provider remains open, including its privacy and cost tradeoffs. Rights declarations remain separate from anchoring. C3/C4/C5 remain future work; M6 and M7 remain deferred; ERN-AI remains outside the core roadmap.
