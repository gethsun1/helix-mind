<p align="center">
  <img src="./helixmindcoverimage.jpg" alt="HelixMind scientific intelligence workstation" width="100%" />
</p>

<h1 align="center">HelixMind</h1>

<p align="center"><strong>An auditable institutional AI infrastructure layer for Research &amp; Innovation.</strong></p>

<p align="center"><a href="./LICENSE">MIT License</a> · <a href="https://github.com/gethsun1/helix-mind/issues">Issues</a> · <a href="./CONTRIBUTING.md">Contributing</a></p>

> **Research software, not medical advice.** HelixMind organises research
> information and transparent reasoning. It does not provide diagnoses,
> treatment recommendations, or validated medical probabilities.

## Product positioning

HelixMind is an **auditable institutional AI infrastructure layer for
Research & Innovation**. Its first implemented vertical is **Research &
Innovation Intelligence**: a persistent research project workflow with
bounded AI planning, literature retrieval, source-linked evidence, deterministic
evidence reasoning, human-controlled research memory, and reproducible outputs.

The existing `Investigation` record is the research project primitive. Its
institutional context comes from the researcher's existing organization
profile. This implementation does not provide multi-tenant institutional
SaaS, organization management, shared institutional workspaces, a university
ERP, or a general workflow platform.

The flagship demonstration question is in biotechnology, particularly
CRISPR-Cas9 and sickle cell disease. This is a bounded demonstration domain,
not a claim that HelixMind is a clinical system. Retrieved literature remains
the evidence source of truth. AI-generated plans are inspectable planning
outputs, not evidence or scientific conclusions. Confidence values are
evidence-system assessments, not clinical probabilities or scientific truth.

## Current status

This status reflects the M4 acceptance verification completed on
2026-09-29. Results below are point-in-time checks; they do not guarantee
future availability of external inference or literature providers.

| Area | Current status |
| --- | --- |
| Research & Innovation Intelligence | Implemented as the first Research & Innovation infrastructure vertical |
| Identity and access | Google authentication, persistent researcher identity, USER/ADMIN roles, protected APIs, owner-scoped investigations |
| Research projects | Investigation as project, research question, profile research context, run IDs, and parent-run lineage |
| Bounded OmegaClaw planning | Structured plan, provider/model attribution, latency, fallback status/reason, safe usage, deterministic fallback when needed |
| Literature and evidence | PubMed and Europe PMC retrieval, normalized records, identifier handling, deduplication, persisted provenance, source-linked evidence |
| Knowledge and reasoning | Claims, entities, relationships, propositions, hypotheses, contradictions, knowledge gaps, deterministic evidence aggregation and traces |
| Persistent research memory | Explicit Human Research Decisions, owner/investigation scope, source provenance, active/inactive state, auditable subsequent-run application |
| Reproducibility and artifacts | Parent/child run lineage, immutable SHA-256 snapshot manifests, Markdown/scientific report/Obsidian exports, authenticated downloads |
| MeTTa / PeTTa boundary | PostgreSQL is canonical; MeTTa is a structured projection and PeTTa validates it |
| M1 — Persistent Research Infrastructure | Persistent research workflow, owner-scoped investigations, literature retrieval, evidence, and reproducible artifacts |
| M2 — Research & Innovation Infrastructure Hardening | Hardened research workflow, ownership, provider attribution, persistent research memory, and reproducibility |
| M3 — Knowledge Graph 2.0 | Investigation-scoped entity detail and graph diff, evidence provenance, snapshot redaction, same-owner and cross-owner isolation |
| M4 — Literature Intelligence 2.0 | Investigation-scoped publication intelligence, auditable relevance, evidence coverage, immutable snapshot contribution comparison, and publication/graph navigation; accepted with 64 backend tests and Playwright/Chromium smoke test passed |

The current dependency audit reports one critical Next.js finding and one
high PostCSS finding. Remediation requires a separate Next.js major-version
upgrade and has not yet been performed. This remains a separate security
maintenance track; no deployment was performed as part of M4.

## M1/M2 verification (2026-09-28)

The backend suite passed with **57 tests**, `npm run build` passed, and
`git diff --check` passed. A real two-run golden workflow used OmegaClaw
planning through ASI Cloud `asi1-mini` without provider fallback. PubMed and
Europe PMC both succeeded on both runs. The researcher explicitly saved a
Human Research Decision; run 2 recorded the active memory in its input
manifest and audit event, and both second-run queries reflected its clinical
priority. Run lineage and owner isolation were checked. The run 2 snapshot
manifest digest was verified by the API, and the downloaded artifact SHA-256
matched both artifact metadata and the response digest header.

The M2 end-to-end workflow ran against the isolated `helixmind_test` database;
the worker and artifact-generation functions were invoked synchronously so
the test did not use the application Redis queue. M1 separately verified the
queue-backed workflow. No production migration or deployment was part of M2.
These checks describe the verified run, not a guarantee about future external
provider availability. The fixed NAL/PLN proof is a separate technical proof;
it is not the production evidence-reasoning pipeline. See the
[runtime notes](./docs/OMEGACLAW_RUNTIME.md) for further boundaries.

## M3 verification — Knowledge Graph 2.0 (2026-09-28)

M3 adds an investigation-scoped entity detail API and provenance neighborhood,
typed relationship inspection, and snapshot graph comparison. Entity identity
remains conservative and deterministic; global aliases are omitted from graph
responses because they do not carry investigation-level provenance. Historical
snapshot API views redact shared entity metadata while preserving the immutable
stored manifests and their original digests. See the
[Knowledge Graph 2.0 design and audit](./docs/KNOWLEDGE_GRAPH_2.0.md).

The isolated PostgreSQL `helixmind_test` database was at repository migration
head. The full backend suite passed with **60 tests**, the frontend production
build passed, and `git diff --check` passed. Database-backed regression tests
cover same-owner cross-investigation and cross-owner isolation, entity detail,
and snapshot graph diff. The real CRISPR/sickle-cell workflow completed with
PubMed and Europe PMC retrieval, a valid immutable snapshot, deterministic
MeTTa output, and successful PeTTa runtime validation. The frontend graph
explorer was also interactively verified against real API data. These results
are point-in-time verification and do not guarantee future external provider
availability. No production migration or deployment was performed as part of
M3 verification.

## M4 verification — Literature Intelligence 2.0 (2026-09-29)

M4 adds investigation-scoped literature intelligence on the existing canonical
publication, evidence, graph, and immutable snapshot records. It provides
canonical publication identity and deduplication, publication evidence
contribution profiles, and auditable relevance using the versioned
`literature-relevance-v1` formula. Relevance is a deterministic investigation
ordering/linkage signal; it is not scientific truth probability, clinical
probability, or evidence confidence. Limited-support labels describe retrieved
evidence coverage and do not imply evidence of absence.

Publication and graph navigation works in both directions while preserving
source provenance and investigation/owner isolation. Snapshot comparison reads
immutable manifests and compares publication contributions reproducibly. The
implementation retains PubMed and Europe PMC as its literature providers.
See the [M4 architecture and API notes](./docs/LITERATURE_INTELLIGENCE_2.0.md)
and the [M4 acceptance report](./docs/M4_LITERATURE_INTELLIGENCE_2.0_REPORT.md).

The accepted verification passed **64 backend tests** and a Playwright/
Chromium smoke test. The real CRISPR–sickle-cell workflow retained 20 canonical
publications, 162 evidence records, 138 reported graph entities, and 13
relationships. Both literature providers succeeded, and all 162 evidence
spans matched their source abstracts. Two valid snapshots were compared;
comparison reproduced 20 retained publications with zero added, removed, or
changed contributions. These are point-in-time results, not guarantees of
future provider availability. No deployment was performed as part of M4.

## Architecture

```text
AUTHENTICATED RESEARCHER
        ↓
Next.js Research Workspace
        ↓ authenticated same-origin proxy
FastAPI API
        ↓
PostgreSQL — canonical identity and research state

RESEARCH EXECUTION (HelixMind research worker via Redis / RQ)
Research Project / Investigation
        ↓
Bounded OmegaClaw-powered Research Planning Agent
        ├─ structured plan + provider/model, latency, fallback and safe usage metadata
        └─ ASI / configured inference provider
        ↓
PubMed + Europe PMC → normalized, persisted literature and provenance
        ↓
Source-linked evidence → knowledge, propositions, hypotheses, gaps, contradictions
        ↓
Deterministic application-level evidence aggregation and reasoning traces
        ↓
Human Research Decision → persistent, scoped ResearchMemory
        ↓
Subsequent research run → immutable SHA-256 snapshot → reproducible artifacts

KNOWLEDGE REPRESENTATION BOUNDARY
PostgreSQL canonical state → structured MeTTa knowledge projection → PeTTa validation

SEPARATE FIXED TECHNICAL PROOF
NAL / PLN deduction over a fixed proof input
```

The API, worker, Redis instance, database identity, service user, logs, and
reasoning runtime are HelixMind-specific. The VPS is shared with unrelated
projects; see [the infrastructure boundary](./docs/INFRASTRUCTURE.md) before
operating a deployment.

### Authentication and authorization

Google verifies the external identity through NextAuth 4. NextAuth maintains a
persistent JWT session and calls the backend identity-sync boundary using a
server-side secret. FastAPI creates or updates the corresponding PostgreSQL
user record. The configured administrator is assigned `ADMIN`; other users are
`USER`.

The PostgreSQL user record is authoritative for role and ownership. Protected
API routes derive the current user from the bearer token, scope investigations
and papers to that user, and allow administrative diagnostics only through a
server-side role dependency. Client-supplied roles, ownership, or credentials
are not trusted. Secrets and provider keys remain outside Git and are never
documented here.

Provider credentials are used only by backend services and are never sent to
the browser. Persisted provider attribution contains safe metadata such as
provider, model, latency, fallback state/reason, and permitted usage fields;
raw credentials are excluded. Research memories are selected by both owner and
investigation, and their application is recorded in run inputs and audit
events.

### Research lifecycle

```text
Research question + research context
        ↓
Investigation / research project
        ↓ queued through Redis / RQ
Bounded OmegaClaw planning → PubMed + Europe PMC retrieval
        ↓
Persisted papers and provenance → exact source-linked evidence
        ↓
Knowledge graph and structured propositions
        ↓
Deterministic evidence assessment → hypotheses / contradictions / gaps / traces
        ↓
Human Research Decision → explicit persistent ResearchMemory
        ↓
Later run applies eligible memory → immutable snapshot → artifact
```

The current worker retrieves and persists source records, extracts exact
abstract claims and evidence, derives explicit propositions, and runs
deterministic application-level evidence aggregation. MeTTa receives a
structured projection of persisted knowledge, and PeTTa validates that
projection. This does not make MeTTa the canonical database or imply that the
fixed NAL/PLN proof runs the production scientific reasoning pipeline. The
system does not generate autonomous scientific conclusions or clinical
recommendations.

### Persistent Research Memory — Human Research Decisions

Researchers can explicitly save a structured decision to an investigation.
Memory rows are PostgreSQL-backed and scoped to both the investigation and its
owner. Each record retains its type, decision text, timestamp, active state,
source run and snapshot when supplied, and audit metadata. Memories can be
deactivated without deleting their history. Free text is retained as the
researcher's recorded decision; the worker applies only the selected supported
memory type, rather than treating it as an unrestricted hidden prompt.

The current supported decisions have deterministic effects:

- **Human clinical priority** adds human and clinical-trial terms to the
  PubMed and Europe PMC search queries and raises the ranking of papers whose
  publication type or MeSH metadata identifies human/clinical evidence.
- **Off-target constraint** adds off-target effects as a required research
  objective and retrieval concept in the subsequent plan.

At run start, the worker loads active memories for the investigation owner,
records the exact memory IDs and decision text in the run input manifest,
which is carried into the immutable run snapshot, and persists a
`research_memory_applied` event with the policy and actions used. The derived
plan, search queries, search filters, paper ranking
reasons, evidence, and reasoning remain inspectable through the existing
workstation provenance chain. The interface can list and deactivate memories,
link them to the originating run/snapshot, and show where a later run applied
them. See the focused implementation and persistence tests in
[`backend/tests/test_research_memory.py`](./backend/tests/test_research_memory.py).

The frontend is deployed through Vercel Git integration: pushed branches can
receive Preview deployments, and the configured production branch updates the
production alias. The API and worker use HelixMind-specific VPS services; see
[deployment and infrastructure notes](./docs/INFRASTRUCTURE.md). M2 verification
did not deploy or change service configuration.

### Phase 3E scientific reasoning

Phase 3E is implemented as an additive extension to the Phase 3D provenance
graph:

- Evidence preserves the canonical paper, exact abstract span, extraction
  method, proposition link, polarity (`SUPPORTS`, `CONTRADICTS`, `NEUTRAL`, or
  `UNCERTAIN`), and extraction signals.
- Stable subject/predicate/object propositions allow evidence from multiple
  papers to be aggregated without reducing claims to free-form text alone.
- Hypotheses use qualified evidence states: `SUPPORTED`, `CONTESTED`, `WEAK`,
  or `UNRESOLVED`. These labels do not mean scientifically true or false.
- Contradictions are created only for opposing evidence attached to the same
  structured proposition. Different paper conclusions are not labelled
  contradictory merely because they differ.
- HelixMind evidence confidence is deterministic and explainable. It combines
  polarity balance, extraction quality, independent supporting sources,
  extraction confidence, and provenance completeness. It is not a clinical
  probability or the probability that a hypothesis is true.
- Knowledge gaps record weak, missing, or contested evidence and may include a
  clearly labelled potential research opportunity. They are not medical advice.
- MeTTa renders propositions, evidence polarity, hypotheses, contradictions,
  and gaps; the existing private PeTTa runtime validates the representation.
  Persisted reasoning traces record the evidence considered, relationships,
  rule, result, confidence, and uncertainty.
- The worker exposes `KNOWLEDGE` and `REASONING` stages and persists events for
  evidence extraction, proposition/hypothesis creation, contradiction detection,
  gap detection, and reasoning completion.

The implemented reasoning rule is `direct_evidence_balance`; a general-purpose
NAL rule library is not claimed as complete. ERN-AI and semantic contradiction
detection remain future boundaries. Phase 4B exports preserve the Phase 3E
distinctions in deterministic, snapshot-labelled artifacts. See [the Phase 3E
design note](./docs/SCIENTIFIC_REASONING.md) and [the research artifact notes](./docs/RESEARCH_ARTIFACTS.md).

The live verification corpus contained 18 genuine retrieved papers and
produced 192 source-linked evidence records, 22 propositions, 22 hypotheses
and 22 reasoning traces, and 6 knowledge gaps. No contradictory evidence was
identified in that corpus, and none was fabricated for demonstration. The 192
evidence records include 19 linked to explicit propositions; 173 remain
source-grounded claims/evidence without a supported deterministic relationship
and therefore are not promoted into hypotheses. See the [Phase 3E audit](./docs/PHASE_3E_REASONING_AUDIT.md)
for the provenance, confidence, contradiction, inference-provider, and
evaluation-gate findings.

## Literature layer

The worker uses official APIs: PubMed ESearch/EFetch and Europe PMC REST search.
Records are normalized into title, abstract, authors, publication date, DOI,
PMID/PMCID, URL, source metadata, and the exact query. Canonical identifiers
and fallback identity rules prevent duplicate paper records. The
`investigation_papers` association retains the search and relevance context.

The current deterministic flagship query is:

```text
PubMed:     ("sickle cell disease"[Title/Abstract]) AND (CRISPR[Title/Abstract] OR "gene editing"[Title/Abstract])
Europe PMC: (TITLE_ABS:"sickle cell disease") AND (TITLE_ABS:CRISPR OR TITLE_ABS:"gene editing")
```

Provider failures are recorded as controlled search failures; a successful
source can be preserved when another source fails. No papers are fabricated.
See [the literature pipeline](./docs/LITERATURE_PIPELINE.md), [knowledge layer](./docs/KNOWLEDGE_LAYER.md), and [inference providers](./docs/INFERENCE_PROVIDERS.md).

## OmegaClaw, PeTTa, and MeTTa

The repository contains two distinct, bounded OmegaClaw capabilities:

1. The investigation worker invokes OmegaClaw-backed research planning and
   persists the resulting structured plan. Provider/runtime failures are
   audited and can fall back to a deterministic search plan that is disclosed
   in the UI and does not assert scientific findings.
2. A constrained local proof runs OmegaClaw Core's plugin/channel mechanism,
   accepts one fixed MeTTa operation, and demonstrates an NAL deduction. It is
   a separate technical proof, not the production evidence-reasoning layer.

The bounded planning integration completed the verified ASI-backed research
workflow. The fixed NAL/PLN proof also passed as a separate technical check;
neither result means OmegaClaw/MeTTa performs all scientific inference.
Provider credentials remain environment-only. See
[the runtime notes](./docs/OMEGACLAW_RUNTIME.md).

## ERN-AI boundary proposal

ERN-AI is not implemented or integrated. The proposed modular boundary is:

```text
Research event → event normalization → ERN-AI significance assessment
               → frequency / strength → confidence → MeTTa representation
               → NAL / PLN reasoning → research-state update
```

Details are in [docs/ERN_AI_INTEGRATION.md](./docs/ERN_AI_INTEGRATION.md).

## API surface

The API prefix is `/api/v1`; protected routes require the authenticated bearer
session. Important routes include:

| Route | Purpose |
| --- | --- |
| `GET /health` | API and PostgreSQL readiness |
| `POST /auth/sync` | Server-side NextAuth identity synchronization |
| `GET/PATCH /me` | Current researcher profile |
| `POST/GET /investigations` | Create and list owner-scoped investigations |
| `GET /investigations/{id}` | Investigation plan, status, and event trace |
| `GET /investigations/{id}/papers` | Paginated owner-scoped papers |
| `GET /investigations/{id}/searches` | Source search records and status |
| `GET /investigations/{id}/evidence` | Exact source-linked evidence and polarity |
| `GET /investigations/{id}/hypotheses` | Qualified hypotheses and evidence balance |
| `GET /investigations/{id}/contradictions` | Explicit opposing evidence pairs |
| `GET /investigations/{id}/knowledge-gaps` | Evidence deficiencies and research opportunities |
| `GET /investigations/{id}/reasoning` | Reasoning summary and persisted results |
| `GET /investigations/{id}/reasoning/trace` | Inspectable proposition-to-result traces |
| `GET/POST /investigations/{id}/memories` | List or explicitly save owner-scoped research decisions |
| `POST /investigations/{id}/memories/{memory}/deactivate` | Deactivate a memory while retaining its audit history |
| `GET/POST /investigations/{id}/runs` | Owner-scoped run lineage and queued reproducible reruns |
| `GET/POST /investigations/{id}/snapshots` | Immutable run snapshots and source manifests |
| `GET /investigations/{id}/snapshots/compare` | Deterministic comparison of two snapshots |
| `GET /investigations/{id}/literature/intelligence` | Investigation literature landscape, contribution paths, duplicate candidates, and limited-support coverage |
| `GET /investigations/{id}/literature/publications/{paper_id}` | Publication contribution profile and auditable relevance inputs |
| `GET /investigations/{id}/literature/publications/{paper_id}/graph` | Investigation-scoped graph contribution for a publication |
| `GET /investigations/{id}/literature/graph/{kind}/{record_id}/publications` | Resolve graph entity, relationship, proposition, or hypothesis support to publications |
| `GET /investigations/{id}/literature/compare` | Compare publication contributions across two immutable snapshots |
| `GET/POST /investigations/{id}/snapshots/{snapshot}/artifacts` | List or generate private Markdown, scientific report, or Obsidian artifacts |
| `GET /investigations/{id}/snapshots/{snapshot}/artifacts/{artifact}/download` | Download a completed owner-scoped artifact |
| `GET /papers/{id}` | Paper detail and investigation provenance |
| `GET /literature/search` | Search the authenticated user's corpus |
| `GET /admin/diagnostics` | Redacted diagnostics for administrators |

## Development and deployment

Prerequisites are Node.js 20+, Python 3.12+, PostgreSQL, and Redis. Use
dedicated non-production database and queue resources. Configure values in
`backend/.env` from the documented keys in `backend/.env.example`; the example
contains placeholders and must not be used as a production configuration.
Frontend and backend environment settings are documented in
`deploy/helixmind-frontend.env.example` and `deploy/helixmind.env.example`.

Install frontend dependencies and start Next.js from the repository root:

```bash
npm install
npm run dev
```

In a separate terminal, create the Python environment, configure the backend,
apply migrations to the configured development database, and start the API:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
PYTHONPATH=. ../.venv/bin/alembic -c alembic.ini upgrade head
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8401
```

Start the worker in another `backend/` terminal using the configured Redis
URL and queue (the example local service uses port 6381):

```bash
PYTHONPATH=. ../.venv/bin/rq worker --url redis://127.0.0.1:6381/0 helixmind-research
```

Run backend tests from `backend/` with `PYTHONPATH=.` (for example,
`PYTHONPATH=. ../.venv/bin/python -m pytest -q`). The hosted frontend uses
Vercel; HelixMind's API, PostgreSQL, Redis/RQ worker and reverse proxy use
HelixMind-specific VPS configuration. The deployment files and
[infrastructure boundary](./docs/INFRASTRUCTURE.md) describe those services;
the VPS also hosts unrelated projects, which are outside this repository and
must remain isolated. The full contributor workflow, migration rules,
scientific data principles, and PR expectations are in
[CONTRIBUTING.md](./CONTRIBUTING.md).

## Repository guide

```text
app/                    Next.js routes, protected workstation, and styles
backend/app/            FastAPI routes, models, queue jobs, literature/knowledge pipeline
backend/migrations/     Alembic environment and versioned schema changes
backend/omegaclaw/      constrained provider/channel and proof configuration
backend/reasoning/      source-grounded MeTTa programs
backend/tests/          API, database, literature, auth, proof, and memory contracts
deploy/                 HelixMind-only systemd, Redis, Nginx, and env examples
docs/                   literature, knowledge, inference, runtime, infrastructure, integration notes
```

## Roadmap

### Completed

- Isolated API, PostgreSQL, Redis, RQ worker, and migration foundation
- Google/NextAuth identity flow, persistent sessions, profiles, roles, and ownership
- Investigation planning lifecycle and traceable event stream
- Real PubMed and Europe PMC ingestion with normalization and provenance
- Constrained OmegaClaw/PeTTa/MeTTa NAL proof

### Completed: Phase 3C — Literature layer

- Provider abstraction for PubMed and Europe PMC
- Deterministic normalization, PMID-first deduplication, persistence, and provenance
- Authenticated search/detail APIs and responsive provenance-aware literature UI

### Completed: Phase 3D — Knowledge layer

- Deterministic abstract extraction with source-grounded claims and evidence
- Provenance-preserving entities, relationships, and bounded graph APIs
- Validated MeTTa projection through the private PeTTa runtime

### Completed: Phase 3E — Scientific reasoning

- Deterministic evidence polarity, structured propositions, qualified hypotheses,
  contradiction pairs, knowledge gaps, and reasoning traces
- Transparent evidence-confidence formula with explicit uncertainty semantics
- MeTTa representation and PeTTa validation for the Phase 3E reasoning facts
- Asynchronous worker lifecycle, persisted reasoning events, protected APIs,
  and investigation/hypothesis/knowledge graph visualizations
- Phase 3E regression and end-to-end corpus tests

### Completed: Phase 4A — Reproducibility foundation

- Investigation run lineage with parent/child reruns, lifecycle status, and
  code, schema, plan, and provider metadata
- Immutable SHA-256 hashed snapshots containing the complete source, evidence,
  reasoning, event, formula, and MeTTa projection manifest
- Owner-scoped run, snapshot, comparison, and artifact-registry APIs
- Automatic run creation and snapshot freezing for completed worker jobs;
  reruns preserve earlier snapshots without destructive mutation
- Deterministic snapshot comparisons for added, removed, and changed records,
  provider metadata, formula versions, and manifest digests

### Completed: Phase 4B — Research artifacts

- Deterministic Markdown investigation reports and machine-readable structured
  scientific reports generated only from immutable snapshot manifests
- Private, owner-scoped artifact registry, queued worker generation, atomic
  storage, SHA-256 content digests, media types, byte sizes, lifecycle status,
  and authenticated downloads
- Obsidian-compatible vault ZIP exports with deterministic filenames, stable
  ordering, paper/evidence/proposition/hypothesis/gap/reasoning notes, source
  links, bibliography, and manifest/provenance files
- Missing identifiers and unavailable source fields remain explicitly missing;
  exports do not fabricate citations or scientific conclusions

### Completed: Phase 4C — Scientific workstation UX

- Research Quest milestone progress and research-health counts derived from
  persisted investigation events and owner-scoped records
- Server-backed evidence explorer filters for polarity, confidence, paper,
  proposition, and provenance completeness
- Hypothesis Lab evidence balance showing supporting and contradictory records
  with source links and explicit confidence semantics
- Snapshot/run controls, artifact generation and download status, and clear
  loading, empty, failed, partial, and responsive mobile states

### Completed: Persistent Research Memory — Human Research Decisions

- Explicit, typed, owner-scoped decisions persisted in PostgreSQL with source
  run/snapshot links, active/deactivated lifecycle, and audit metadata
- Human-clinical memory changes PubMed and Europe PMC queries and relevance
  ranking; off-target memory changes subsequent plan objectives and search
  concepts
- Memory IDs and applied policy are captured in run input manifests and linked
  to persisted planning, search, evidence, and reasoning records
- Workstation controls to save, review, and deactivate decisions; verified as
  part of the 57-test M1/M2 baseline

## Advanced Track 04 — Build the AI Infrastructure Layer

The current implementation follows the **Research & Innovation
Infrastructure** direction. Its project primitive is an Investigation;
bounded OmegaClaw planning structures literature searches; retrieved sources
become persisted literature and source-linked evidence; deterministic
application-level reasoning produces inspectable hypotheses, gaps, and traces;
researchers save explicit Human Research Decisions as persistent memory; and
run lineage, immutable snapshots, and authenticated artifacts make the work
auditable and reproducible.

Option A remains the architectural umbrella. Option B, Research & Innovation
Intelligence, is the implemented vertical. Option C, Institutional Asset
Intelligence / RWA and digital asset infrastructure, is future scope and is
not implemented.

## Roadmap

### Completed through M4

- Google authentication, persistent researcher identity, USER/ADMIN roles,
  protected APIs, and owner-scoped research projects
- Investigation research context, bounded OmegaClaw planning, safe provider
  attribution, and deterministic fallback handling
- PubMed and Europe PMC retrieval, normalization, identifier handling,
  deduplication, and source provenance
- Source-linked evidence, claims, propositions, hypotheses, contradictions,
  knowledge gaps, deterministic evidence aggregation, and reasoning traces
- PostgreSQL canonical state with structured MeTTa projection and PeTTa
  validation; separate fixed NAL/PLN technical proof
- Human-controlled, owner/investigation-scoped ResearchMemory with save and
  source provenance, active/inactive state, audit records, and application on
  subsequent runs
- Parent/child run lineage, immutable SHA-256 snapshot manifests, deterministic
  Markdown and structured scientific reports, Obsidian-compatible exports,
  authenticated artifact registry and downloads
- M1 baseline recovery and M2 workflow hardening, verified 2026-09-28 (see
  [M1/M2 verification](#m1m2-verification-2026-09-28))
- M3 typed, provenance-aware entity exploration and snapshot graph diff,
  verified 2026-09-28 (see [M3 verification](#m3-verification--knowledge-graph-20-2026-09-28))
- M4 investigation-scoped literature intelligence, auditable relevance,
  limited-support coverage, immutable snapshot contribution comparison, and
  publication/graph navigation, verified 2026-09-29 (see
  [M4 verification](#m4-verification--literature-intelligence-20-2026-09-29))

### Roadmap

- **M1–M4: COMPLETE** — baseline, workflow hardening, knowledge graph, and
  literature intelligence are verified.
- **M5 — Semantic Extraction Pilot: COMPLETE / ACCEPTED** — source-grounded
  candidates, deterministic validation, provenance, scoped graph projection,
  and reproducibility are verified in the isolated CRISPR/sickle-cell workflow.
  See [M5 acceptance evidence](docs/M5_SEMANTIC_EXTRACTION_PILOT.md).
- **C0 — Scientific IP Assetization discovery: COMPLETE** — architecture
  reviewed; see the [C0 architecture and discovery package](docs/C0_SCIENTIFIC_IP_ASSETIZATION.md).
- **C1 — Private Provenance & Rights Foundation: COMPLETE** — private,
  owner-scoped asset versions, provenance verification, explicit rights
  declarations, and audit events. This does not adjudicate legal ownership;
  see the [C1 implementation](docs/C1_PRIVATE_PROVENANCE_RIGHTS_FOUNDATION.md).
- **C2 — Verifiable Provenance Credentials / Anchors: FUTURE / OPTIONAL**.
- **C3 — License Workflow / Rights Operations: FUTURE**.
- **C4 — External Registry / Marketplace Adapter: FUTURE**.
- **C5 — Commercial Operations: FUTURE**.
- **M6 Domain Adapters: DEFERRED**.
- **M7 Inference Observability: DEFERRED**.

### Deferred and future milestones

- **C2 — Verifiable Provenance Credentials / Anchors:** optional future work;
  no chain or credential issuer is selected.
- **C3 — License Workflow / Rights Operations:** future work requiring legal
  and business decisions.
- **C4 — External Registry / Marketplace Adapter:** future work requiring a
  documented integration and rights model.
- **C5 — Commercial Operations:** future work.

- **M6 — Domain Adapters:** configurable domain support and validated domain
  fixtures, starting with the current biotechnology demonstration
- **M7 — Inference Observability:** expanded provider/model, latency, usage,
  retry, fallback, failure, health, and cost metadata with secret redaction

ERN-AI is outside the core HelixMind roadmap. Public publishing,
leaderboards, and public research sharing are outside the implemented scope;
artifact downloads remain private and owner-scoped.

## How to contribute

Start with [CONTRIBUTING.md](./CONTRIBUTING.md), then consult the focused
design notes for [literature](./docs/LITERATURE_PIPELINE.md),
[OmegaClaw runtime](./docs/OMEGACLAW_RUNTIME.md),
[infrastructure](./docs/INFRASTRUCTURE.md), and the
[ERN-AI proposal](./docs/ERN_AI_INTEGRATION.md). Use a focused branch and PR;
do not commit directly to `main`.

## License

HelixMind is open source under the [MIT License](./LICENSE).
