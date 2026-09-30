# C0 — Scientific IP Assetization: Discovery and Architecture

**Status:** Discovery proposal; no assetization behavior is implemented.
**Scope:** Architecture only. No schema migration, endpoint, token, wallet, chain, marketplace integration, or production change is part of C0.

## 1. Executive architecture

HelixMind should treat assetization as an optional layer above its scientific intelligence and reproducibility system. The canonical research graph and cited literature remain the scientific record. A candidate asset is a reference to a particular completed run, immutable snapshot, and generated artifact, accompanied by provenance and explicit rights declarations. It is not a new scientific truth store.

The first useful assetization product is a **provenance package**, not a transferable token: a versioned artifact plus a machine-readable manifest that identifies its exact research snapshot, content digest, generation contract, source lineage, uncertainty, and rights declarations. A later, separately authorized attestation may anchor a digest and non-sensitive identifiers externally. Ownership or license tokens should remain out of scope until parties establish the legal instrument, rights chain, governance, and transfer consequences.

**Proposed boundary:** C1 may add private, owner/investigation-scoped asset records and a rights declaration workflow over existing snapshots/artifacts. It must not claim to adjudicate rights. Chain registration, public visibility, transfer, licensing execution, and marketplaces are separate later decisions.

Labels in this document mean: **Existing** = verified repository behavior; **Proposed** = architecture recommendation; **External** = third-party or legal dependency; **Open** = decision or fact not yet established.

## 2. Existing HelixMind infrastructure to reuse

Verified in this repository at the M5 acceptance revision:

| Existing capability | Current implementation and assetization relevance |
| --- | --- |
| Research identity and isolation | `User` and `Investigation.owner_id`; APIs scope investigations to owner, with the existing ADMIN exception. This is an access boundary, not shared institutional ownership or a rights registry. |
| Source corpus and lineage | Canonical `Paper`, `InvestigationPaper`, `ResearchSearch`, source queries, DOI/PMID/PMCID where supplied, and retrieval timestamps. Literature records can be third-party works and must not be represented as user-owned content by default. |
| Evidence and knowledge graph | Investigation-linked `Claim`, `Evidence`, `Proposition`, `Relationship`, `Hypothesis`, `Inference`, `Contradiction`, and `KnowledgeGap`, with source spans, polarity, and links. Confidence fields are evidence-system assessments, not scientific certainty. |
| Semantic extraction | `SemanticExtraction` preserves candidates separately from evidence/claims, with source run, extraction run, publication/evidence/claim links, model/provider/version, content hash, and validation state. Only validated candidates project into existing relationships. |
| Run lineage | `InvestigationRun` has run number, parent run, code/schema version, plan hash, input manifest, provider metadata, and status. This supports identifying the research execution that produced a snapshot. |
| Immutable snapshot | `ResearchSnapshot` is a frozen manifest tied uniquely to an investigation run. `build_snapshot_manifest` serializes the investigation input, run metadata, literature/searches, claims, evidence, graph/reasoning records, contradiction records, events, safe provider metadata, and artifact contract. |
| Digest mechanism | `canonical_json` sorts keys and uses compact JSON; `digest_json` SHA-256 hashes its UTF-8 bytes. Per-record digests are also included. `metta_digest` hashes the rendered graph projection separately. Snapshot reads report stored-manifest digest validity; scoped/redacted API views have a distinct response digest. |
| Artifact registry and export | `ResearchArtifact` binds snapshot, artifact type/format, generator/schema versions, content digest, manifest digest, status, visibility, and private storage key. Markdown, scientific report, and Obsidian ZIP exports are generated from snapshots and downloaded through authenticated APIs. |
| Authenticated APIs and UI | FastAPI routes use authenticated sessions and owner-scoped investigation checks. The Next.js research workspace includes investigation, literature, graph, hypothesis, and semantic extraction views. The current artifact UX is private export/download, not publication or rights administration. |

Relevant implementation references: `backend/app/models.py`, `backend/app/research_reproducibility.py`, `backend/app/research_artifacts.py`, `backend/app/routes/reproducibility.py`, `backend/app/routes/knowledge.py`, `backend/app/routes/reasoning.py`, `backend/app/routes/semantic_extraction.py`, `backend/app/security.py`, `backend/app/routes/investigations.py`, `docs/RESEARCH_ARTIFACTS.md`, `docs/M5_SEMANTIC_EXTRACTION_PILOT.md`.

### Important existing limits

- The snapshot is immutable after creation, but its manifest includes some changing investigation-scoped records, including all events and currently queried graph state. A snapshot binds the exact serialized state captured; it does not by itself establish that every source item was licensed for redistribution or that the scientific conclusions are correct.
- Snapshot manifest SHA-256 covers the canonical serialized manifest. Artifact `content_digest` covers generated bytes. The snapshot manifest records an artifact contract, not the future asset record. Neither digest is a signature, timestamp authority, legal title record, or proof of authorship.
- Artifact visibility currently defaults to `PRIVATE`; storage is not a public web directory. Existing API scoping is a strong starting point, but no asset rights, collaborators, institutional tenant model, public revocation registry, or wallet identity exists.
- Snapshot creation captures the graph state of the investigation at freeze time; the run ID and lineage describe execution, but later graph writes can exist outside an earlier snapshot. Asset references must always resolve to the frozen snapshot and artifact, not a live investigation view.
- C0 should not modify M5 extraction behavior or promote model candidates into an asset eligibility decision.

## 3. Candidate asset classes

| Candidate | What it represents; uniqueness and reproducibility | Evidence and possible rights holder | Legal/licensing value and representation | Main risks |
| --- | --- | --- | --- | --- |
| **Reproducible research artifact/package** — recommended first | One generated report, structured export, or package identified by artifact ID, generator/schema version, snapshot ID, and byte digest. Reproduce by re-running the declared generator against the same frozen manifest and compatible generator contract; exact byte identity must be checked rather than assumed across runtime changes. | Snapshot manifest, source IDs/spans, run lineage, generator metadata, limitations, and digest. Possible rights holder depends on employment, funding, collaboration, source licenses, and jurisdiction. | Rights declaration and distribution license can be meaningful after review. Off-chain private artifact plus optional digest attestation is appropriate. An NFT is unnecessary for simple integrity/provenance. | Third-party publication content, sensitive data, non-deterministic formatting/runtime, mistaken claims of ownership, confidentiality leakage. |
| **Scientific IP record** | A rights/provenance dossier referring to one artifact version and its declared subject matter. Unique by HelixMind ID plus version; reproducibility comes from linked snapshot and artifact. | Same lineage plus contributor and rights declarations, dependency schedule, and claim/conflict state. Owner must be declared by an authorized human or institution, not inferred by HelixMind. | Could support diligence or rights management; the record itself does not create title. Usually hybrid only if a public, non-sensitive registry is justified. It is not automatically an NFT. | False title, incomplete coauthor/institution claims, patent/publication timing, mistaken implication that registration validates science. |
| **Research license** | A specific grant over an identified artifact/version and a defined scope, parties, term, territory, permitted uses, restrictions, and governing instrument. Unique as a license instance, not simply a label attached to the artifact. | Rights holder authority, signed or otherwise legally effective instrument, artifact/version digest, and amendment/termination events. | Licensing can be meaningful, but enforceability comes from the governing agreement and applicable law. Store the authoritative agreement off-chain; optional verifiable reference or access credential. A transferable token alone is not a license. | Ambiguous scope, unauthorized grant, transfer mistaken for sublicense, terms changing while a token persists, consumer/commercial/regulatory rules. |
| **Research credential / attestation** — plausible early external anchor | A signed statement that an identified digest existed or that a defined process/validation check was recorded at a stated time. Unique by issuer, subject digest, schema, and issuance identifier. | Snapshot/artifact digests and issuer identity; evidence can be referenced without exposing its text. Issuer attests to a narrow process fact, not truth or title. | Useful for provenance verification. Prefer signed off-chain credential initially; optional chain anchoring after privacy and issuer governance review. Usually not an ownership NFT. | Issuer key compromise, stale/revoked claims, overclaiming “validated,” public correlation, unverifiable source data. |
| **Dataset/evidence package** | A versioned, curated dataset with schema, inclusion rules, source and transformation lineage, and digest. | Source evidence and dataset dependency/license inventory; control may belong to multiple providers or institutions. | Potentially licensable if rights, privacy, consent, and database rights permit. Keep payload access-controlled off-chain; a digest or access entitlement may be hybrid. | Copyright/database rights, personal/sensitive data, consent and purpose limits, redistribution restrictions, irreversible disclosure. |
| **Research-derived discovery or hypothesis** — defer | A bounded proposition or hypothesis linked to exact evidence and contradictory evidence in a snapshot. Unique only when carefully scoped with definitions and version. Reproducible as a record of interpretation, not as proof the finding is true. | Supporting and contradictory evidence, extraction provenance, uncertainty, validation method, publication and retraction state. Rights may be absent or unclear; discoveries/facts, expression, inventions, and patentable subject matter differ by law. | Better represented as a provenance attestation or research record. Licensing/tokenization is premature without a protectability and rights assessment. | Misleading certainty, prior art/public disclosure, patent novelty loss, contested inventorship, scientific update/retraction, false endorsement. |

No object qualifies merely because it has a row, digest, high confidence value, or successful semantic validation. Reproducibility and scientific support are distinct from entitlement to commercialize.

## 4. Scientific validity, provenance, authorship, ownership, and rights

These are separate assertions with separate evidence:

| Concept | Meaning in this architecture | What it does not establish |
| --- | --- | --- |
| Scientific validity | Quality and current support of a research claim under an identified method and body of evidence; may remain contested and change. | Ownership, authorship, patentability, licensing authority, or commercial permission. HelixMind does not certify universal scientific truth. |
| Provenance | Traceable record of inputs, transformations, runs, snapshot, artifact, and digest. | Who legally owns any input or output, or whether the input use was permitted. |
| Authorship/contribution | A declared and potentially disputed account of human or organizational contributions to a defined version. | Legal inventorship, copyright ownership, employment entitlement, or consent to transfer. |
| Ownership | A declared claim to specified rights in specified subject matter, with asserted basis and supporting documentation. | A conclusion HelixMind can infer from account identity, artifact creation, or on-chain control. |
| License | Permission granted by an authorized rights holder under specified terms. | Transfer of title, patent grant, sublicensing right, or rights not stated in the instrument. |
| Commercial rights | Authority to use, distribute, commercialize, sublicense, or monetize defined material, subject to contract and law. | A default property of scientific output, public data, or a HelixMind download. |
| On-chain registration | A ledger entry/attestation binding an identifier and selected metadata/digest to a transaction and key at a point in time. | Scientific correctness, identity of a natural person without verification, legal title, enforceable license, priority, or absence of prior claims. |

HelixMind must label rights fields as **declared**, **documented**, **reviewed**, or **disputed** with the basis and reviewer recorded. “Reviewed” means a specified human/process review occurred; it is not a guarantee of legal title. LLMs may extract candidate metadata for human review but must never determine ownership, inventorship, or commercial licensing eligibility.

## 5. Eligibility framework and conceptual lifecycle

Eligibility should be a deterministic completeness gate plus explicit human rights declarations. It is not a scientific quality score or legal opinion. Required checks for a candidate version:

1. Stable asset family identity and immutable version identifier.
2. Completed source run and valid immutable snapshot belonging to the same investigation.
3. Exact generated artifact record, completed status, artifact digest, and matching snapshot manifest digest; verify stored bytes when available.
4. Provenance manifest identifying source snapshot, run lineage, generator/schema versions, evidence lineage, and relevant semantic extraction/validation records.
5. Author/contributor declarations and role/consent state; distinguish account creator from creator of underlying IP.
6. Rights declaration naming declared owner, subject matter, asserted basis, evidence/document reference, reviewer state, and unresolved conflicts.
7. Dependency schedule for publications, abstracts, datasets, code, third-party assets, and licenses/restrictions; absence of detected dependency is not proof of absence.
8. Confidentiality, privacy, consent, publication/patent timing, funder/employer, and data protection review where relevant.
9. Intended use and proposed license fields, including commercial use and derivatives; explicitly mark unknown or not granted.
10. Scientific state disclosure: supporting and contradictory evidence, limitations, uncertainty, corrections/retractions known to the record, and date of assessment.
11. Access/visibility classification and confirmation that no private payload or PII will be placed in public metadata.
12. No unresolved ownership dispute or documented prohibition on the intended distribution/registration action.

Proposed lifecycle (concept only; transitions and enforcement are not implemented):

`DRAFT → RESEARCH_ONLY → PROVENANCE_READY → ASSETIZATION_ELIGIBLE → REGISTERED/ANCHORED → LICENSED`

`REVOKED` and `SUPERSEDED` are status events on an existing version, not deletion. `RESEARCH_ONLY` means the object exists for internal research but is not offered as an IP asset. `PROVENANCE_READY` means lineage and digests are complete, not rights-cleared. `ASSETIZATION_ELIGIBLE` requires declarations and checks above, with explicit reviewer/authority. `REGISTERED/ANCHORED` records a selected external registration; it does not change science or title. `LICENSED` refers to a particular active grant, not to the asset generally. A rights dispute, source retraction, correction, or supersession creates an append-only event and may suspend future offers without erasing prior history.

Eligibility is scoped to an exact asset version and intended action (private provenance, public attestation, commercial license, etc.); a package eligible for internal verification may not be eligible for public distribution.

## 6. Proposed provenance and snapshot/digest relationship

Proposed object chain:

```text
Investigation (owner-scoped research context)
  └─ InvestigationRun (execution + parent lineage)
       └─ ResearchSnapshot (immutable canonical manifest + SHA-256)
            └─ ResearchArtifact (type/format + generator contract + content SHA-256)
                 └─ AssetVersion (proposed rights/provenance wrapper)
                      └─ optional external anchor / credential reference
```

An `AssetVersion` should bind—not copy as a second truth source—the immutable `snapshot_id`, `manifest_digest`, `artifact_id`, `content_digest`, artifact type/format, generator/schema contract, and a versioned asset provenance manifest. It should record the investigation scope and its owner at creation for authorization/audit, but must not treat that owner as the declared legal owner. The selected artifact is the asset payload; the snapshot digest anchors its scientific/research lineage. Recompute and compare both digests before issuing a future external attestation.

The provenance manifest should have an explicit schema/version and canonical serialization. It should include only disclosed identifiers and digests, source/reference identifiers and licenses where known, run parent identity, source state date, generator contract, and disclosure of evidence/contradiction/retraction status. It should not duplicate full literature or evidence text. The existing snapshot has record digests and a manifest digest; C1 should not quietly change their formula. Any future asset-specific canonicalization needs its own versioned contract and test vectors.

**Digest semantics:** a matching SHA-256 shows byte/representation integrity relative to the supplied digest, assuming secure implementation. It does not establish who created the bytes, when they existed, who owns them, or that they are scientifically correct. Public chain anchoring adds a public timestamp/order and tamper-evident reference under that network's assumptions, with permanence and privacy tradeoffs.

## 7. Rights declaration model

For each asset version, record declarations separately from system-derived provenance:

- `contributors`: stable internal actor IDs where appropriate, declared names/roles, contribution basis, declaration source, consent/acknowledgement state. Keep PII and identity documents off-chain.
- `declared_owner`: person or institution identifier and whether claim is individual, joint, employer, funder, or another basis; never populate automatically from `User.id`.
- `ownership_basis`: human-entered category and optional private evidence/document reference; record no legal conclusion.
- `rights_scope`: exact version/material covered, including excluded third-party components.
- `license_declaration`: SPDX or other identifier only where appropriate, human-readable terms/URI, commercial use, derivative use, attribution, redistribution, sublicensing, term/territory, and exceptions. License terms need versioned immutable records.
- `third_party_material`: dependency IDs, source URL/identifier, known license/restriction, included/excluded status, and unresolved status.
- `rights_status`: `UNDECLARED`, `DECLARED`, `DOCUMENTED`, `REVIEWED`, `DISPUTED`, `REVOKED`, or `UNKNOWN`, with actor/time/reason and append-only history.
- `conflict_status`: asserted claims and dispute references; status does not decide the dispute.

The system should preserve the submitted declaration and later corrections as events. Replacing a license creates a new license/version or revocation event; it must not rewrite what a historical anchor referred to. A clickable license URI is not proof that the grantor had authority.

## 8. Versioning, correction, contradiction, and retraction

Every asset version is immutable and binds one artifact and one snapshot. A new completed run, new snapshot, changed artifact bytes, material rights update, or materially revised interpretation creates a new version or a new asset family if its subject matter changes. Use `family_id` plus monotonically allocated version/parent-version link; do not overwrite old digest, rights declaration, or anchor references. Metadata corrections produce an append-only correction event and, if they change the anchored payload/meaning, a new version.

Contradictory evidence remains visible because snapshots include evidence polarity and explicit contradiction records, and exports already distinguish uncertainty. A later contradictory source does not invalidate the historical fact that a version was generated. It should trigger a new research snapshot and version whose scientific-status summary identifies the changed evidence set. Retraction metadata should include the retracted source identifier, notice/source, discovery time, and affected asset versions; it must be reported as a provenance event rather than silently deleting the source. HelixMind currently has no verified retraction monitoring service, so automated detection is an open dependency.

`SUPERSEDED` says a newer version is preferred for current use; it does not erase or necessarily disprove the earlier version. `REVOKED` should specify whether the reason concerns rights, security, source integrity, or an external registry status. If an external anchor cannot be removed, publish a privacy-safe correction/revocation reference where technically possible and retain its transaction identity. Revocation of an attestation is not deletion of public chain history.

## 9. Off-chain/on-chain hybrid architecture

| Off-chain in HelixMind or controlled storage | Candidate public anchor only after review |
| --- | --- |
| Full artifact, evidence, publication/abstract text, datasets, graph, semantic extraction, detailed provenance, rights instruments, ownership evidence, PII, confidential/patent-sensitive research, access control, dispute documentation. | Random or non-identifying asset/version identifier; digest of a deliberately defined public manifest or artifact; schema/version; coarse lifecycle/revocation pointer; issuer/registry key or DID only if governance supports it; timestamp/network transaction reference. |

Never place PII, private dataset content, confidential research, full publication text, sensitive metadata, access tokens, or irreversible secrets on-chain. A hash of low-entropy/sensitive content can be guessed or correlated; use random IDs and avoid exposing predictable hashes when disclosure itself is sensitive. An IPFS/content-addressed URI is not automatically private or erasable; availability, pinning, encryption/key lifecycle, and metadata leakage need separate decisions.

Recommended progression: private signed provenance record first; then an optional digest attestation on a selected network or credential ecosystem; only then assess tokenized ownership/licensing after legal and operational review. Chain adapters should be replaceable and should not be part of scientific data creation or validation. If no chain provides useful verification beyond existing signed artifacts, remain off-chain.

## 10. NFT, attestation, license record, and tokenized ownership

| Representation | Best fit | Advantages | Limits / when not to use |
| --- | --- | --- | --- |
| NFT / non-fungible token | A uniquely identified digital representation when public discoverability or controlled transfer of the token itself is a real requirement. | Persistent token ID and observable transfer history on a chosen network. | Token transfer does not transfer copyright, patent rights, data access, or license unless separate enforceable terms make that consequence clear. Avoid for private datasets, provisional findings, or simple provenance. |
| Verifiable credential / attestation | “Digest X was recorded/issued by issuer Y under process/schema Z at time T.” | Non-transferable claim semantics can communicate process/provenance without pretending title; can be signed off-chain and selectively disclosed depending on format. | Issuer governance, key lifecycle, schema, revocation, verifier support, privacy, and truth limits must be explicit. Not a legal ownership determination. |
| License record | Specific rights grant from an authorized grantor to a grantee over defined version/material and conditions. | Represents terms, parties, scope, duration, and revocation/amendment linkage. | The contract/instrument is primary; on-chain record may be only a pointer/receipt. Transferability, sublicensing, identity and consumer/security regulation require review. |
| Tokenized ownership representation | A token intended to represent transferable legal/economic rights. | Could automate or expose transfer state when an enforceable, legally supported structure exists. | Highest legal/regulatory, custody, identity, governance, securities/financial, dispute, and mismatch risk. Not appropriate as an early C1/C2 assumption. |
| Hybrid | Off-chain scientific package and legal instrument with signed credential or optional chain anchor. | Separates sensitive payload and enforceable terms from public integrity reference. | Multiple systems of record require durable identifiers, availability, key governance, and clear rules for conflicting state. |

Chain/network selection should follow requirements, not preference: privacy and metadata leakage, permanence/revocation, identity and key recovery, transaction cost and throughput, enterprise custody, verifier and wallet reach, credential/attestation support, token standards if later needed, interoperability, governance/upgrades, operational security, and applicable jurisdiction/regulation. C0 selects no network or standard.

## 11. BASIX / external marketplace fit

**Confirmed from BASIX public materials checked 2026-09-30:** the BASIX Omniversity homepage describes a Web3 & AGI incubator/developer LMS, MeTTa/Web3 learning and cohorts, verifiable credentials (Open Badges v2 described as “on-chain-ready”), an IP marketplace where participants register build outputs as owned/licensable IP, and its DICE co-ownership model. The same public page presents institutional credentials, software projects, and marketplace/IP ambitions. Sources: [BASIX Omniversity homepage](https://www.basix.market/), [BASIX ecosystem page](https://www.basix.market/ecosystem).

**Not confirmed:** no public API specification, asset schema, authentication method, chain/network contract, supported research-data format, rights-verification procedure, credential issuer/verifier details, upload/privacy policy, or integration terms were found in the public materials reviewed. Marketing descriptions are not proof that any specific API, marketplace workflow, token standard, or legal process exists. We should not infer these capabilities.

**Conceptual fit:** HelixMind could eventually export a provenance package or signed attestation for a research artifact. BASIX might provide a downstream discovery/listing or credential/marketplace workflow if its product supports scientific artifacts and the parties agree on rights and data boundaries. HelixMind would need a documented ingestion/registration API, identity and rights model, accepted identifiers/digests, status/revocation behavior, privacy/security terms, and stable link/ownership semantics. BASIX would likely need (to be confirmed) a non-sensitive metadata manifest, artifact/version identity, digest, provenance evidence, rights declarations, licensing terms, contributor acknowledgements, and a method to verify the issuer.

Before any integration, confirm: Does BASIX accept externally generated assets or only assets built in its cohorts? Is “ownership” a platform record, token, contract, or legal assignment? Which network and token/credential standards are actually live? Can a user register a non-transferable provenance record? What are API, auth, rate, lifecycle, dispute, takedown, and revocation contracts? How are institutions, coauthors, employer/funder rights, confidential data, and third-party sources handled? Which party is responsible for legal review and claims? Integration must remain optional; HelixMind must retain a vendor-neutral export and internal record.

## 12. Preliminary threat model

| Threat | Affected layer / consequence | Conceptual mitigation (not implemented by C0) |
| --- | --- | --- |
| Fraudulent ownership or unauthorized assetization | Rights declaration/registry; false title claim, infringement, disputes. | Explicit authorized human declaration, documented basis, conflict state, institution/funder review, provenance audit; no automatic ownership inference. |
| Plagiarism or stolen research | Artifact creation and rights review; misattribution or disclosure of another party's work. | Contributor declarations, source lineage, similarity/institutional review where appropriate, dispute/takedown path; provenance is evidence, not adjudication. |
| Third-party copyrighted literature or restricted dataset | Packaging/distribution; infringement or license breach. | Dependency inventory, inclusion/exclusion controls, license review, minimal citation/identifier metadata, access restrictions; never assume retrieval implies redistribution rights. |
| Confidential research, personal data, private dataset leakage | Storage/export/chain; irreversible exposure, privacy or contractual harm. | Off-chain access controls, pre-export classification/review, minimization, no sensitive on-chain URIs/hashes, encrypt private payload, tested redaction. |
| Metadata manipulation or artifact substitution | Manifest, storage, external anchor; verifier sees mismatched or misleading content. | Bind immutable artifact and snapshot digests, verify downloaded bytes, signed manifests, append-only events, independent re-verification. |
| Hash/canonicalization mismatch | Provenance integration; false validation or false rejection. | Version canonicalization/schema; publish test vectors; bind algorithm and encoding; recompute at registration and verification; separate snapshot and content digests. |
| Wallet/key compromise or lost key | External anchor/credential; unauthorized signing or inability to update/revoke claims. | Key custody policy, hardware-backed keys/multisig where warranted, rotation/recovery and issuer revocation, no wallet key as sole source of identity/title. |
| Ownership transfer or license dispute | Token/marketplace/contract; ledger state conflicts with actual rights. | Legal instrument defines transfer effects; explicit parties and scope, consent and review, dispute state, chain treated as registry evidence only. |
| Retraction, new contradiction, changed interpretation | Scientific layer and public claims; stale asset misleads. | Immutable versions, visible contradictions/status events, correction/retraction notices, links to newer snapshots, no deletion of prior history. |
| Misleading scientific claims or overclaiming validation | Attestation, marketplace description; reputational or safety harm. | Narrow attestation schema, source/uncertainty disclosure, human scientific review, ban implication that hash/chain proves truth or clinical efficacy. |
| Tokenization of non-owned IP / legal uncertainty | Rights, token, marketplace and jurisdictions; invalid grant or regulated activity. | Defer transfer/economic tokens pending qualified legal/business review, rights-chain verification, jurisdictional and regulatory analysis. |
| Cross-owner/investigation data exposure | API/storage/export; confidentiality breach. | Reuse owner and investigation scoping on every endpoint/object lookup; test cross-scope paths; separate public proof metadata from private payload. |

## 13. Conceptual data model (proposed, not migrations)

Only the following new concepts appear justified. Reuse `ResearchSnapshot` and `ResearchArtifact` as immutable source records rather than introduce duplicate versions of them.

| Entity | Purpose and key fields | Immutability / scope / provenance |
| --- | --- | --- |
| **ScientificAsset** | Stable asset family identity: `id`, `investigation_id`, `created_by_user_id`, `asset_type`, `title/label`, `visibility`, `created_at`. It is a container for versioned representations, not title. | Identity and initial scope immutable; mutable display/administrative state only through audited events. Owner/investigation scoped. Creator is the HelixMind record creator, not presumed IP owner. |
| **AssetVersion** | One immutable package binding `asset_id`, version number, parent version, `snapshot_id`, `artifact_id`, manifest/content digests, schema/canonicalization version, declared scientific status as-of time, status, created time. | Immutable payload references and digests. Must verify snapshot/artifact belong to same investigation and artifact points to that snapshot. Each update creates a new version. |
| **AssetRightsDeclaration** | Version-scoped assertions: contributors, declared owner, basis, rights scope, license reference/terms, commercial/derivative permissions, third-party dependencies, review/conflict status, declaring actor/time, evidence references. | Submitted declaration is immutable; correction/review/revocation represented by linked event or new declaration revision. Sensitive documents off-chain, access controlled. Not legal adjudication. |
| **AssetEvent** | Append-only lifecycle/history: event ID, asset/version, type, actor, timestamp, reason, prior/new status, referenced evidence, external transaction/credential reference if any. | Append-only and auditable; scope follows asset. Supports correction, supersession, dispute, retraction, anchor, license, and revocation events. |
| **AssetAnchor** | Optional external registration/attestation reference: version, network/issuer, chain ID or credential type, transaction/subject ID, anchored digest/schema, timestamp, status/revocation locator. | Record what was submitted and returned; append state changes, never treat anchor as title. Avoid storing wallet PII or private URI. Defer creation until a later chain/credential phase. |

No separate `AssetProvenance` entity is needed initially: a versioned manifest plus existing snapshot/artifact references can carry provenance, with future normalization only if queries or independent provenance changes justify it. No separate `AssetLicense` is required if the rights declaration points to an immutable license record/instrument; a distinct license entity becomes justified when grants have independent parties, lifecycle, transfer, multiple assets, or amendments. `AssetEvidenceLink` is initially redundant because source lineage is in the snapshot and can be referenced by IDs; introduce only if precise version-scoped evidence selection cannot be represented in the manifest. No token balance/owner table should be introduced absent a selected representation and legal model.

## 14. Future API surface (conceptual)

All routes should require an authenticated user and verify investigation ownership on every request. Existing ADMIN access follows current policy but must be auditable; external/public verification should expose only a separately reviewed public manifest. Every child lookup must constrain by both asset and investigation to prevent IDOR/cross-owner access.

| Method and path | Purpose / request and response concept | Validation and immutable fields |
| --- | --- | --- |
| `POST /api/v1/investigations/{investigation_id}/assets` | Create a `DRAFT` asset family from a completed snapshot and completed artifact; request type, label, snapshot/artifact IDs, intended visibility. Return asset/version IDs and digest references. | Auth + owner scope; snapshot and artifact must belong to same investigation, artifact complete and digest-valid. Creator/scope, source references, digests, and version identity immutable. |
| `GET /api/v1/investigations/{investigation_id}/assets` | List scoped assets with current version/status and summary. | Owner scope; no cross-investigation filtering shortcuts. |
| `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}` | Read family, versions, current declarations and status summary. | Asset must belong to path investigation; redact private fields per actor. |
| `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}/versions/{version_id}` | Retrieve exact version manifest and verification result. | Verify association, digests, schema support, artifact access; disclose that integrity is not title/scientific truth. |
| `POST /api/v1/investigations/{investigation_id}/assets/{asset_id}/rights-declarations` | Add declaration/revision with parties, basis category, license scope, dependencies, intended use, attachments by private reference. | Explicit human submitter, authorization, required acknowledgements, no LLM auto-approval; preserve immutable submitted terms. |
| `POST /api/v1/investigations/{investigation_id}/assets/{asset_id}/events` | Authorized correction, dispute, supersession, withdrawal/revocation, or human review event. | Typed event, reason, actor and evidence required; append-only. State transitions validated in future implementation. |
| `GET /api/v1/investigations/{investigation_id}/assets/{asset_id}/provenance` | Return verified chain of investigation/run/snapshot/artifact/source identifiers and digests. | Scope check; verify digest against stored canonical bytes; separate private and exportable manifest. |

Do not add `/anchors` write or mint endpoints in C1. A later registration adapter can add a narrowly scoped request/receipt API after network, issuer, privacy, and key governance decisions. Do not expose generic public asset listing or marketplace endpoints by implication.

## 15. Roadmap and milestone placement

1. **C0 — Discovery and architecture (this deliverable):** verified code/schema map, asset/rights boundaries, threat model, external questions, no implementation.
2. **C1 — Private provenance and rights foundation:** only after C0 review; focused conceptual schema for asset families, immutable versions, declarations and audit events; bind existing snapshots/artifacts; digest verification; owner isolation; private manifest/export; eligibility completeness checks; no legal adjudication, chain, wallet, token, public directory, marketplace, or production migration until separately reviewed and planned.
3. **C2 — Verifiable provenance credentials/anchors (optional):** choose attestation versus chain and network only after requirements, privacy assessment, issuer/key governance, canonical manifest, revocation/correction semantics, and test environment. A no-chain signed credential remains valid candidate.
4. **C3 — License workflow / rights operations:** only after legal/business confirmation of parties, terms, authority, identity, transfer, dispute, and relevant regulatory obligations. License documents remain authoritative off-chain.
5. **C4 — External registry/marketplace adapter:** BASIX or another partner only after API/contract/security/rights fit is documented; vendor-neutral interface and export; no provider dependency.
6. **C5 — Commercial operations and analytics:** only if C3/C4 demonstrate a legitimate use case; governance, service operations, dispute handling, reporting, and any market or economic analytics separately scoped.

M6 Domain Adapters and M7 Inference Observability remain **deferred**, independent roadmap tracks. C0 does not require them; asset provenance can record existing schema/provider metadata without expanding M7. They may be reconsidered later if an asset class requires domain-specific rights/evidence checks or more run instrumentation. ERN-AI remains removed from the core roadmap; historical documentation can remain unchanged.

## 16. Open questions and human/business/legal decisions

- Which initial object matters commercially: report/package, dataset, provenance credential, or something else? Who is the buyer/user and what decision does assetization enable?
- Is the first institutional context individual researcher, employer/university, consortium, funder, or company? Repository ownership is currently per researcher, not an organization workspace.
- What jurisdictions, employment/funding agreements, publication policies, data protection rules, patent/publication timing, and research ethics regimes apply?
- What legal instrument, if any, backs declared ownership and license grants? Who can verify authority and resolve joint/institutional claims?
- Which contributors must consent, and how are corrections, disputes, transfer, sublicense, termination, and posthumous/organizational changes handled?
- Which source/publication/dataset licenses permit content in exported artifacts? Is the asset a citation/link, excerpt collection, transformed dataset, or full text?
- What integrity assurance is required: HelixMind private digest, signing authority, independent timestamp, public chain, credential issuer, or multiple?
- Which metadata is safe to disclose, and what threat model applies to digest correlation and metadata URI permanence?
- How will source retraction notices be discovered and validated? What is the human review SLA and the public correction process?
- Does BASIX accept external scientific artifacts, offer a documented API, support non-transferable attestations, and provide rights/legal governance suitable for research institutions? Public sources do not answer these.
- Are tokens necessary at all? If so, what exact right transfers, what jurisdiction applies, and what consumer, financial, securities, tax, custody, and marketplace obligations follow?

These decisions require business/product owners, participating institutions/contributors, security/privacy review, and qualified legal counsel. C0 records design options; it is not legal advice and does not resolve jurisdiction-specific rights.

## 17. C1 exit criteria

Before C1 implementation begins, reviewers should agree on the initial asset class, owner/institution scope, rights declaration authority, acceptable content and visibility, immutable version/digest contract, dispute/retraction handling, and whether C1 is private only. C1 should be accepted only when all reads and writes preserve existing investigation isolation, every version resolves to a verified existing snapshot/artifact, declarations are visibly non-adjudicative, prior versions/events remain auditable, and no chain or marketplace is required to use the core asset record.
