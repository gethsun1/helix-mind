<p align="center">
  <img src="./helixmindcoverimage.jpg" alt="HelixMind scientific intelligence workstation" width="100%" />
</p>

<h1 align="center">HelixMind</h1>

<p align="center"><strong>An evidence-led scientific intelligence workstation for traceable research investigations.</strong></p>

<p align="center"><a href="./LICENSE">MIT License</a> · <a href="https://github.com/gethsun1/helix-mind/issues">Issues</a> · <a href="./CONTRIBUTING.md">Contributing</a></p>

> **Research software, not medical advice.** HelixMind organises research
> information and transparent reasoning. It does not provide diagnoses,
> treatment recommendations, or validated medical probabilities.

## Project proposition

HelixMind applies OmegaClaw/MeTTa reasoning to a practical scientific research
workflow. A question becomes an owner-scoped investigation, an explicit
research plan, a queued literature search, and a provenance-preserving record
of source material.

The flagship demonstration domain is biotechnology, especially CRISPR. CRISPR
connects genetics, molecular biology, and medicine; it produces rich evidence
relationships that are understandable in a public demonstration. The domain
is a proving ground for traceable scientific reasoning, not a claim that
HelixMind is a CRISPR-only or clinical system.

The non-negotiable principle is: **retrieved literature is the evidence source
of truth**. LLMs may help plan or interpret work, but generated text is not
automatically evidence. Confidence values are evidence-system assessments, not
clinical probabilities.

## Current status

This index reflects the repository and isolated runtime inspected on 2026-08-24.
“Verified” means supported by source inspection, tests, or a live check; it
does not imply that every future research capability is complete.

| Area | Current status |
| --- | --- |
| Next.js 14 / TypeScript workstation | Implemented; Vercel frontend responds at `https://helix-mind-green.vercel.app/` |
| FastAPI API | Implemented; live health check responds through the public HelixMind endpoint |
| PostgreSQL / Alembic | Implemented with HelixMind migrations and scientific schema |
| Redis / RQ | Implemented as isolated `helixmind-redis.service` and `helixmind-research` queue |
| Google OAuth / NextAuth 4 | Implemented with persistent JWT session and backend identity sync |
| User profiles and roles | Implemented; PostgreSQL is authoritative for researcher identity and USER/ADMIN role |
| Investigation ownership | Implemented; API queries enforce owner scope, with explicit admin diagnostics access |
| PubMed and Europe PMC | Implemented with real retrieval, normalization, PMID/DOI/PMCID deduplication, ranking, and provenance |
| OmegaClaw planning | Implemented in the worker path, with controlled provider failure handling |
| OmegaClaw / PeTTa / MeTTa NAL proof | Verified as a constrained local proof, separate from the full evidence-reasoning product |
| Entity extraction, knowledge graph, evidence assessment, contradictions, hypotheses, synthesis, export | Not implemented; roadmap work |
| Public API route and TLS | Live-check verified for the current HelixMind host; deployment configuration remains HelixMind-specific |

## Architecture

```text
PUBLIC CLIENT
    │ HTTPS
    ▼
Next.js workstation on Vercel
    │ NextAuth session + same-origin backend proxy
    ▼
Google OAuth / researcher identity sync
    │ bearer session token
    ▼
HelixMind FastAPI API
    │ owner-scoped investigation and literature routes
    ▼
PostgreSQL ◄───────────────┐
    │ users, investigations, events, papers, provenance
    │                        │
    └── queued job ──► Redis / RQ ──► HelixMind worker
                                      │
                                      ├─ OmegaClaw research planning
                                      ├─ PubMed / NCBI retrieval
                                      └─ Europe PMC retrieval

Separate constrained proof runtime:
OmegaClaw Core → PeTTa → MeTTa → NAL/PLN proof
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

### Research lifecycle

```text
CURRENT PRODUCT PATH
Question → investigation record → RQ queue → OmegaClaw plan
         → PubMed / Europe PMC retrieval → normalization → deduplication
         → persisted paper-to-investigation provenance and event trace

VERIFIED SEPARATE PROOF
Source-grounded facts → MeTTa representation → NAL/PLN deduction

NEXT RESEARCH LAYERS
Evidence extraction → entities and knowledge graph → contradiction analysis
→ hypotheses and knowledge gaps → confidence assessment → synthesis → export
```

The current worker can retrieve and persist source records; it does not yet
turn abstracts into validated claims or autonomous scientific conclusions.

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
See [the literature pipeline](./docs/LITERATURE_PIPELINE.md).

## OmegaClaw, PeTTa, and MeTTa

The repository contains two distinct capabilities:

1. The investigation worker invokes OmegaClaw-backed research planning and
   persists the resulting structured plan. Provider errors are fail-closed and
   do not leak credentials.
2. A constrained local proof runs OmegaClaw Core's plugin/channel mechanism,
   accepts one fixed MeTTa operation, and demonstrates an NAL deduction. It is
   not yet a general autonomous research agent and is not equivalent to the
   future evidence-reasoning layer.

The proof uses configured Gemini first and Groq fallback. Provider credentials
are environment-only. The verified proof output is an evidence-system truth
value, not medical efficacy or clinical probability. See
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
| `GET /papers/{id}` | Paper detail and investigation provenance |
| `GET /literature/search` | Search the authenticated user's corpus |
| `GET /admin/diagnostics` | Redacted diagnostics for administrators |

## Development

Prerequisites are Node.js 20+, Python 3.12+, PostgreSQL, and Redis. Use
dedicated non-production database and queue resources.

```bash
npm install
npm run dev

python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
PYTHONPATH=. ../.venv/bin/alembic -c alembic.ini upgrade head
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8401
PYTHONPATH=. ../.venv/bin/rq worker --url redis://127.0.0.1:6381/0 helixmind-research
```

Run backend tests from `backend/` with `PYTHONPATH=.`. The full contributor
workflow, migration rules, scientific data principles, and PR expectations
are in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Repository guide

```text
app/                    Next.js routes, protected workstation, and styles
backend/app/            FastAPI routes, models, queue jobs, providers, pipeline
backend/migrations/     Alembic environment and versioned schema changes
backend/omegaclaw/      constrained provider/channel and proof configuration
backend/reasoning/      source-grounded MeTTa programs
backend/tests/          API, database, literature, auth, and proof contracts
deploy/                 HelixMind-only systemd, Redis, Nginx, and env examples
docs/                   infrastructure, literature, runtime, and integration notes
```

## Roadmap

### Completed

- Isolated API, PostgreSQL, Redis, RQ worker, and migration foundation
- Google/NextAuth identity flow, persistent sessions, profiles, roles, and ownership
- Investigation planning lifecycle and traceable event stream
- Real PubMed and Europe PMC ingestion with normalization and provenance
- Constrained OmegaClaw/PeTTa/MeTTa NAL proof

### In progress / next: Phase 3C — Literature layer

- Broaden source strategy while preserving deterministic normalization
- Improve retrieval observability and source-specific metadata
- Establish the evidence-ready contract for downstream reasoning

### Phase 3D — Knowledge layer

- Extract entities and relationships from source material
- Persist inspectable knowledge/evidence graph structures
- Connect graph views to investigation provenance

### Phase 3E — Scientific reasoning

- Supporting and contradictory evidence
- Hypotheses, knowledge gaps, confidence semantics, and synthesis
- Transparent MeTTa/NAL/PLN updates and exports

### Future / experimental tracks

- ERN-AI event-processing adapter and research-state signals
- Obsidian, Markdown, and structured report export
- Additional literature providers and domain adapters
- Rich graph and reasoning visualizations

## How to contribute

Start with [CONTRIBUTING.md](./CONTRIBUTING.md), then consult the focused
design notes for [literature](./docs/LITERATURE_PIPELINE.md),
[OmegaClaw runtime](./docs/OMEGACLAW_RUNTIME.md),
[infrastructure](./docs/INFRASTRUCTURE.md), and the
[ERN-AI proposal](./docs/ERN_AI_INTEGRATION.md). Use a focused branch and PR;
do not commit directly to `main`.

## License

HelixMind is open source under the [MIT License](./LICENSE).
