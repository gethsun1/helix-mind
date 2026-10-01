# HelixMind Project Documentation

**Submission profile:** Track 4 (Advanced) — Build the AI Infrastructure Layer<br>
**Product focus:** AI infrastructure for auditable, persistent, reproducible research<br>
**Demonstration:** CRISPR-Cas9 / sickle-cell literature workflow<br>
**Status:** Feature-frozen submission build; no external production provenance provider configured

## 1. Executive summary

HelixMind is an auditable AI infrastructure layer for Research & Innovation. It connects bounded agent planning to real scientific literature, source-linked evidence, structured knowledge, deterministic evidence reasoning, explicit researcher decisions, and reproducible outputs. An Investigation is the persistent project boundary. Its owner-scoped records, run lineage, snapshots, and artifacts preserve which inputs and decisions contributed to a research result.

The implementation combines a Next.js research workspace, FastAPI services, PostgreSQL canonical state, and Redis/RQ background execution. OmegaClaw is used for constrained research planning. PubMed and Europe PMC are literature sources. Deterministic extraction and reasoning operate on persisted source records; semantic extraction is a bounded model-assisted pilot whose candidates are validated before graph projection. MeTTa is a structured knowledge projection, and PeTTa validates the representation.

The CRISPR-Cas9 / sickle-cell workflow exercises these infrastructure boundaries using a real literature domain. HelixMind is not a clinical system. Scientific IP provenance is a secondary foundation: private assets can bind rights declarations and provenance records to immutable research artifacts, while production external anchoring, marketplace operation, licensing execution, and tokenization remain future work.

## 2. Problem

AI-assisted research can leave a gap between a generated answer and the evidence or decisions behind it. Literature may be fetched in one tool, notes stored elsewhere, and subsequent prompts may not preserve the exact inputs, researcher choices, or output version. This makes it difficult to inspect the provenance of a claim, compare research runs, or reproduce a report from the same captured state.

Institutional research also needs boundaries around ownership, access, and persistence. A useful system must scope work to a researcher and project, retain evidence source references, distinguish model output from scientific evidence, and preserve research state without implying that an AI system has established scientific truth or legal ownership.

## 3. Solution

HelixMind treats an Investigation as a durable research project. A bounded planning step proposes objectives and searches. Literature providers return real publications; source text is stored with provenance. Deterministic extraction builds claims, evidence, entities, relationships, and propositions. Evidence reasoning calculates inspectable qualified states from persisted evidence. Researchers can record explicit decisions as Human Research Memory. Subsequent runs record which memory was applied.

Runs carry parent/child lineage and are frozen as SHA-256 manifests. Comparisons operate on those snapshots; report artifacts are generated from frozen manifests, not a later mutable investigation view. This links the question, plan, sources, evidence, graph, reasoning, decisions, and output into one reviewable research trace.

## 4. Target users

- **Researchers and research teams** who need a structured literature workflow and traceable evidence.
- **Research software and data teams** building persistent agent workflows that must preserve inputs, transformations, and outputs.
- **Universities and innovation groups** exploring auditable AI infrastructure for research operations.
- **Scientific IP and technology-transfer stakeholders** evaluating how reproducible artifacts and declared rights information could support later provenance workflows.

The current product has authenticated researcher accounts and owner-scoped Investigations. It does not implement shared multi-tenant institutional workspaces, institutional role hierarchies, or a university ERP.

## 5. Track 4 alignment

The official Track 4 (Advanced) brief is **Build the AI Infrastructure Layer**. It calls for practical tools using SingularityNET's Omega agent infrastructure / Hyperon AGI stack for universities, businesses, and community ecosystems, and lists Dev/Scale Support, Fractional CTO Agent, and RWA / Digital Asset Infrastructure options.

HelixMind's **primary alignment** is Research & Innovation intelligence as AI infrastructure. OmegaClaw-powered planning operates inside a bounded workflow that persists retrieval, evidence, researcher decisions, and reproducible outputs. It demonstrates an agent infrastructure pattern for sustained, auditable institutional research work. The CRISPR-Cas9 / sickle-cell workflow is the demonstration domain, not the product category.

The **secondary alignment** is scientific IP asset provenance and rights infrastructure. The current model records private research assets, versions, rights declarations, provenance checks, and audit events. This may provide an adapter boundary for future digital-asset ecosystems; it does not implement the full RWA option, marketplace operations, or tokenization. HelixMind does not claim all Track 4 options.

## 6. End-to-end workflow

```text
Research question
  → Investigation and bounded OmegaClaw planning
  → PubMed / Europe PMC retrieval
  → Persisted publications and source-linked evidence
  → Knowledge graph and structured propositions
  → Deterministic evidence reasoning and traces
  → Explicit Human Research Decision / scoped memory
  → Child research run and immutable snapshot
  → Snapshot comparison and reproducible artifact
  → Optional private scientific asset/provenance record
```

1. The authenticated researcher creates an Investigation with a question and research context. The API scopes access by owner.
2. The worker runs a bounded OmegaClaw planning path. Structured objectives, query terms, provider/model attribution, latency, and fallback status are retained. A deterministic fallback can keep retrieval bounded when planning is unavailable; it does not make scientific findings.
3. PubMed and Europe PMC retrieval normalizes records and source identifiers, records query/source metadata, and associates papers with the Investigation. Partial provider failure is recorded; no papers are fabricated.
4. Deterministic extraction records claims and evidence with publication identity and source spans. Entities and relationships form an investigation-scoped graph. Structured propositions support qualified hypotheses, contradictions, gaps, and reasoning traces.
5. A bounded semantic-extraction run may propose relations from persisted abstract evidence. The service stores candidates separately and applies deterministic source, vocabulary, mention, and provenance validation. Only valid candidates can project as relationships linked to existing source claims. Model candidates do not become evidence or claims.
6. A researcher explicitly saves supported Human Research Decisions. Memory is owner- and Investigation-scoped, has active/inactive state and audit history, and can affect only supported planning/retrieval behavior. The run records the IDs and applied policy.
7. A completed run is captured in a SHA-256 immutable snapshot. Deterministic comparison reports record changes between two snapshots. Markdown, structured report, and Obsidian-compatible exports read the frozen manifest.
8. An optional private asset version can bind a completed artifact and snapshot digest with rights declarations and audit events. This record does not establish legal title or provide external public proof.

### Frontend demonstration paths

The authenticated research workspace exposes these investigation-scoped records through contextual routes:

- `/investigations/{id}` — Investigation overview, evidence explorer, reasoning, Human Research Memory, run lineage, snapshots, and generated artifacts.
- `/investigations/{id}/literature` — literature contribution, immutable literature comparison, bounded semantic-extraction candidates, validation and rejection reasons, source evidence spans, provider/model metadata, and graph projection links.
- `/knowledge?investigationId={id}` — graph records, evidence provenance, and snapshot graph comparison.
- `/investigations/{id}/assets` — private ScientificAsset versions, snapshot/artifact bindings, canonical digests, rights declarations, integrity checks, local/test anchor references, and audit events.

Asset creation uses an existing completed snapshot and artifact. Rights information is an explicit researcher declaration. The deterministic `test/local` reference can be inspected and verified locally; it is not independent or public proof. Scientific validity and legal ownership remain not assessed.

## 7. Architecture

```text
Researcher
  │
  ▼
Next.js / TypeScript workspace (Vercel)
  │ authenticated same-origin proxy
  ▼
FastAPI API ─────────────────── PostgreSQL canonical state
  │                                      ▲
  └── Redis / RQ worker ─────────────────┘
          ├── OmegaClaw planning / configured inference provider
          ├── PubMed and Europe PMC clients
          ├── deterministic evidence, knowledge, and reasoning services
          ├── semantic extraction validation
          └── snapshot and artifact generation

Representation boundary: PostgreSQL → MeTTa projection → PeTTa validation
```

The browser uses a protected workspace and same-origin backend proxy. NextAuth manages Google identity/session flow; a server-side identity sync establishes the PostgreSQL user record. FastAPI authorization is based on the persisted user and owner scope. The worker uses Redis/RQ for background research work and stores canonical records in PostgreSQL.

PostgreSQL is authoritative for identity, literature associations, evidence, graph and reasoning records, runs, memories, snapshots, artifacts, and private scientific assets. MeTTa is a derived structured projection. PeTTa validates its form. A separate constrained OmegaClaw/MeTTa/PeTTa proof demonstrates a fixed NAL/PLN operation; it is not the production evidence-reasoning pipeline.

Deployment separates the Vercel frontend from HelixMind-specific API, PostgreSQL, Redis, and worker services on a VPS. Deployment details and service boundaries are maintained in [Infrastructure documentation](INFRASTRUCTURE.md).

## 8. AI / OmegaClaw integration

OmegaClaw supports bounded planning in the investigation workflow. Planning output is structured and observable: provider/model attribution, latency, fallback state/reason, and safe usage metadata are available. Runtime or provider failure can produce a disclosed deterministic search plan. Plan output directs retrieval; it is not evidence, a diagnosis, or a scientific conclusion.

A separate fixed technical proof exercises a constrained OmegaClaw plugin/channel path and NAL/PLN deduction over a fixed input. It provides a narrow integration demonstration only. HelixMind does not claim a general autonomous scientist, broad NAL/PLN rule coverage, or that MeTTa/PeTTa executes production literature reasoning.

Semantic extraction is model-assisted and bounded by a source run and evidence cap. Inputs come from persisted source evidence in a verified snapshot. Provider output is retained with provider/model/version and hashes, then validated deterministically. Provider generation itself is not claimed to be deterministic. See [OmegaClaw runtime](OMEGACLAW_RUNTIME.md) and [M5 acceptance](M5_SEMANTIC_EXTRACTION_PILOT.md).

## 9. Literature and evidence layer

The implemented literature sources are PubMed ESearch/EFetch and the Europe PMC REST API. Retrieved records are normalized with available title, abstract, authors, publication date, DOI, PMID/PMCID, source URL, provider metadata, and query context. Canonical identity uses supplied identifiers and conservative fallback matching. Records are associated with an Investigation, and provider failures are visible in the search state.

Deterministic extraction links claim and evidence rows to the source publication and exact abstract text/location where available. The evidence record preserves extraction method, polarity and assessment signals. Retrieved literature remains the evidence source of truth. Missing identifiers or source details stay missing; they are not fabricated. Full-text ingestion is not part of the demonstrated pipeline.

M4 literature intelligence adds investigation-scoped publication contribution and coverage information, an auditable deterministic relevance signal, graph/publication navigation, and immutable snapshot contribution comparisons. Relevance and coverage describe the stored research corpus; they do not represent scientific truth or evidence of absence. See [Literature pipeline](LITERATURE_PIPELINE.md) and [M4 report](M4_LITERATURE_INTELLIGENCE_2.0_REPORT.md).

## 10. Knowledge graph

The investigation-scoped graph connects publication-backed claims and evidence with entities, typed relationships, propositions, hypotheses, contradictions, and gaps. Graph APIs and views preserve owner and Investigation scope. Evidence remains the source-level link; higher-level records and reasoning traces refer back to evidence identifiers.

The M3 graph explorer exposes entity detail, typed relationships, provenance neighborhoods, and snapshot graph comparison. Conservative deterministic entity identity avoids asserting cross-investigation aliases where provenance is not established. M5 semantic candidates can add a validated relationship to an existing source claim; the pilot does not create entities, evidence, or propositions from model output. See [Knowledge layer](KNOWLEDGE_LAYER.md) and [Knowledge Graph 2.0](KNOWLEDGE_GRAPH_2.0.md).

## 11. Semantic extraction

The accepted semantic-extraction pilot reads abstract-backed evidence tied to a completed source run and immutable snapshot. A provider proposes relation candidates. The validator checks shape and vocabulary, source/evidence/claim scope, exact source-span containment, offsets, entity references, explicit mentions, lexical relation cues, and self-relations. Candidate rows retain model provenance, validation state, rejection reasons, and hashes.

Only validated candidates project to existing graph relationships, linked to their source claim/evidence. A valid candidate means it passed the defined structural and provenance checks; it is not a measure of scientific truth, causality, clinical probability, or consensus. In the accepted checkpoint, 4 candidates across completed attempts yielded 1 valid and 3 rejected; one valid relation was projected. The fixed evidence slice and provider generation make this a bounded pilot, not general semantic coverage.

## 12. Reasoning model

The production reasoning path uses deterministic application-level aggregation over persisted evidence. Polarity is `SUPPORTS`, `CONTRADICTS`, `NEUTRAL`, or `UNCERTAIN`. A proposition provides a structured subject/predicate/object key. Hypothesis states (`SUPPORTED`, `CONTESTED`, `WEAK`, `UNRESOLVED`) qualify evidence state rather than declare truth. Contradiction records require opposing evidence attached to the same proposition. Knowledge gaps describe weak, missing, or contested retrieved support.

The current rule is `direct_evidence_balance`. A trace records evidence considered, support and opposition, relationships, rule, result, confidence, and uncertainty. The confidence value is a deterministic evidence-system score based on polarity balance, extraction quality, source independence, and provenance completeness. It is not calibrated as probability of truth, clinical probability, study quality, or treatment efficacy. Limited source coverage is not evidence that no evidence exists. Known reasoning and extraction limitations are detailed in [Scientific reasoning](SCIENTIFIC_REASONING.md) and [the Phase 3E audit](PHASE_3E_REASONING_AUDIT.md).

## 13. Human Research Memory

ResearchMemory stores explicit Human Research Decisions, not an unrestricted hidden prompt. Records belong to an owner and Investigation and retain decision type/text, timestamp, active state, optional source run/snapshot links, and audit metadata. A researcher can deactivate a decision while preserving its history.

Supported decisions have bounded deterministic effects on subsequent planning/retrieval. Active memory IDs, policy, and actions are captured in the run input manifest and applied-memory audit events. Researchers remain responsible for deciding whether a saved priority or constraint is scientifically appropriate.

## 14. Reproducibility and snapshots

Research runs retain identifiers, parent-run lineage, code/schema and planning metadata, input manifest, provider metadata, and lifecycle status. A completed run is frozen into a canonical JSON snapshot with SHA-256 manifest digest and record-level information. Later reruns create new runs and snapshots; they do not mutate earlier snapshots.

Snapshot comparison deterministically compares frozen records and reports added, removed, or changed contributions and digest validity. Artifact generation consumes the immutable manifest and records generator/schema version, snapshot manifest digest, output content digest, media type, size, and private storage key. Supported outputs are Markdown, structured scientific report JSON, and Obsidian-compatible ZIP. Downloads are authenticated and owner-scoped. A digest supports integrity checking; it is not a signature, trusted timestamp, external ledger entry, proof of authorship, or legal title.

## 15. Scientific IP asset provenance

The implemented private foundation includes a `ScientificAsset` record, immutable `AssetVersion` bindings to a research snapshot and completed artifact, researcher-declared rights data, provenance checks, audit events, and version-bound canonical digests. It is scoped to the existing Investigation and access control. Rights declarations are statements recorded by a user; HelixMind does not adjudicate legal ownership or licensing authority.

A deterministic `test/local` provider supports local anchor creation and verification. It creates a locally reproducible reference and is not public external proof. C2B reviewed external options and documented a production strategy; the production-capable provider remains unresolved and no external timestamp, blockchain, ledger, BASIX, or marketplace proof is configured.

Future adapter work could connect the scientific artifact/provenance model to an external registry or marketplace such as BASIX.Market, and later support ownership/co-ownership synchronization, licensing workflows, token issuance, or commercial operations. Those capabilities are not implemented. No NFT minting, live tokenization, licensing execution, marketplace integration, or blockchain anchoring is claimed. The potential asset is a provenance-backed digital research/IP artifact and its associated declared rights representation, not a CRISPR gene. See the [C0 discovery](C0_SCIENTIFIC_IP_ASSETIZATION.md), [C1 implementation](C1_PRIVATE_PROVENANCE_RIGHTS_FOUNDATION.md), [C2 boundary](C2_EXTERNAL_PROVENANCE_ANCHOR.md), and [C2B strategy](C2B_PRODUCTION_PROVENANCE_STRATEGY.md).

## 16. Security, isolation, and boundaries

Authentication begins with Google identity via NextAuth; server-side identity synchronization connects the session to a PostgreSQL user. The backend derives the user and role from authenticated credentials. Owner-scoped queries protect Investigations and related records; client-supplied ownership or role values are not authoritative. Provider credentials remain server-side. Artifact storage is private, and downloads pass through authenticated APIs.

The app separates frontend deployment from API/worker/database services. Development, tests, and migrations must use isolated resources. The C2B verification used an isolated PostgreSQL test database and reports no production database or service changes. See [Infrastructure](INFRASTRUCTURE.md), [Contributing](../CONTRIBUTING.md), and the repository [security maintenance note](../SECURITY.md).

Scientific boundary: literature is evidence; a plan is not. Confidence and hypothesis status are qualified system outputs. The product does not diagnose, prescribe, certify scientific truth, or make legal rights determinations. Public research sharing and institutional multi-tenant administration are outside implemented scope.

## 17. Verification evidence

The latest supplied C2B verification record (2026-10-01) reports:

- Isolated PostgreSQL test database confirmed and upgraded to Alembic head `c2a1b2c3d4e5`.
- Full backend suite: **86 passed**; focused C1/C2 checks: **11 passed**.
- Frontend production build and migration verification passed.
- `git diff --check` passed.
- No production database/services changed; no commit or push was performed by the C2B verification session.
- External production provenance remains unresolved; local/test provider is not presented as public proof.

The M5 acceptance report additionally records a real CRISPR/sickle-cell retrieval workflow with 20 canonical publications and 162 evidence rows; bounded semantic extraction accepted one candidate and projected one source-linked relationship; original and resulting snapshot digests were verified. Its backend suite reported 75 passed and a frontend build passed at that checkpoint. These are distinct acceptance checkpoints; counts are not combined or presented as one test run. Current final verification results are reported alongside the submission changes.

## 18. Known limitations

- External AI provider and literature API availability, latency, and output can change.
- OmegaClaw planning is bounded; deterministic fallback does not provide an AI result.
- Literature coverage is limited to PubMed and Europe PMC and, in the demonstrated pipeline, abstract-backed evidence.
- Deterministic extraction and lexical polarity rules can miss paraphrases, context, population differences, or scientific disagreement.
- Semantic extraction covers a bounded evidence slice and depends on model generation; validation improves provenance and structure but does not establish truth.
- Evidence confidence is not calibrated probability. Duplicate evidence and incomplete proposition-level source roll-up constrain interpretation.
- The MeTTa projection / PeTTa validation boundary and fixed NAL/PLN proof are narrower than a general reasoning runtime.
- Researcher-entered rights declarations are not legal review. Local provenance anchors are not external attestations; the production provider is unresolved.
- npm audit reports critical Next.js and high PostCSS advisories; see `SECURITY.md` for deployment relevance and maintenance action.

## 19. Future roadmap

The core research infrastructure, knowledge graph, literature intelligence, semantic-extraction pilot, and private scientific asset provenance foundation are complete for this submission. The C2B external provenance strategy is complete, but its production provider is unresolved.

Licensing operations, external production provenance, registry/marketplace adapters, ownership synchronization, commercial operations, and tokenization are future work. M6 and M7 are deferred; ERN-AI is outside the core roadmap. None is part of the current submission implementation.

## Quick start and operation notes

For local work, use Node.js 20+, Python 3.12+, PostgreSQL, and Redis. Copy `backend/.env.example` to a local-only environment file, configure development service URLs and provider credentials as needed, and keep secrets out of Git. Install dependencies with `npm install` and `python -m pip install -r backend/requirements.txt` in a Python virtual environment. Run the frontend with `npm run dev`.

For backend operation, first migrate a dedicated development database with Alembic from `backend/`, start the FastAPI application using the documented local environment, and run the Redis/RQ worker against a dedicated development Redis. Full commands and contributor test workflow are in [CONTRIBUTING.md](../CONTRIBUTING.md) and [Infrastructure documentation](INFRASTRUCTURE.md). Never direct development migrations at production resources.
