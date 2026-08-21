<p align="center">
  <img src="./helixmindcoverimage.jpg" alt="HelixMind scientific intelligence workstation" width="100%" />
</p>

<h1 align="center">HelixMind</h1>

<p align="center"><strong>An evidence-led scientific intelligence workstation for traceable research investigations.</strong></p>

<p align="center">
  <a href="./LICENSE">MIT License</a> ·
  <a href="https://github.com/gethsun1/helix-mind/issues">Issues</a> ·
  <a href="./docs/INFRASTRUCTURE.md">Infrastructure</a>
</p>

> **Research software, not medical advice.** HelixMind supports literature
> retrieval, evidence organisation, and transparent reasoning. It does not
> provide clinical diagnoses, treatment recommendations, or validated medical
> probabilities.

## What is HelixMind?

HelixMind turns a scientific question into a durable investigation record. It
is designed so that literature, provenance, structured knowledge, reasoning,
and the eventual synthesis remain inspectable rather than hidden behind a
model response.

Its core principle is: **LLMs help plan, interpret, extract, and summarise;
retrieved literature is the evidence source of truth.** MeTTa/NAL reasoning
operates on explicit, source-grounded statements. A system confidence value is
an evidence assessment, never a clinical probability.

## Verified capabilities

| Capability | Status |
| --- | --- |
| Next.js scientific workstation UI | Implemented; deployed separately on Vercel |
| FastAPI API and local health endpoint | Verified on `127.0.0.1:8401` |
| Isolated PostgreSQL schema and Alembic migrations | Verified |
| Isolated Redis queue and RQ worker | Verified |
| Real PubMed and Europe PMC ingestion | Verified with the flagship question |
| Paper normalization, PMID/DOI deduplication, provenance links | Verified |
| OmegaClaw + PeTTa + MeTTa NAL proof | Verified in a constrained local runtime |
| Evidence extraction, hypotheses, contradictions, graph, synthesis, export | Planned; not yet complete |
| Public reverse proxy, TLS, Vercel API connection | Intentionally not configured yet |

The current literature stage returns actual API records and persists source
metadata. It does not fabricate papers, claims, evidence scores, or medical
conclusions.

## System design

```text
                     ┌──────────────────────────────┐
                     │       Next.js workstation     │
                     │  question · activity · graph  │
                     └──────────────┬───────────────┘
                                    │ HTTPS (planned production route)
                                    ▼
                     ┌──────────────────────────────┐
                     │          FastAPI API          │
                     │  investigations · events      │
                     └──────────────┬───────────────┘
                                    │ enqueue
                                    ▼
                     ┌──────────────────────────────┐
                     │      Redis + RQ worker        │
                     │   isolated research jobs      │
                     └───────┬───────────────┬───────┘
                             │               │
              real records  │               │ structured reasoning
                             ▼               ▼
         ┌───────────────────────┐  ┌───────────────────────┐
         │ PubMed · Europe PMC   │  │ OmegaClaw · PeTTa      │
         │ search · fetch · parse│  │ MeTTa · NAL / PLN      │
         └───────────┬───────────┘  └───────────┬───────────┘
                     │                          │
                     └────────────┬─────────────┘
                                  ▼
                     ┌──────────────────────────────┐
                     │          PostgreSQL           │
                     │ investigations · papers       │
                     │ evidence · entities · links   │
                     └──────────────────────────────┘
```

### Evidence lifecycle

```text
Scientific question
  → investigation queued
  → literature plan and source search
  → normalized, deduplicated papers with provenance
  → evidence and entity extraction                 (next)
  → source-grounded MeTTa knowledge                (next)
  → NAL/PLN inferences and contradiction handling  (next)
  → hypotheses, gaps, synthesis, graph, export     (next)
```

## Architecture and isolation

HelixMind is an isolated tenant: it has its own service account, environment
file, PostgreSQL database, Redis instance, RQ queue, log paths, and private
reasoning runtime. The API and Redis bind only to loopback at this stage.

| Component | Implementation | Current boundary |
| --- | --- | --- |
| Frontend | Next.js 14 + TypeScript | Vercel deployment; API wiring pending |
| API | FastAPI + Pydantic + SQLAlchemy | `127.0.0.1:8401` |
| Database | PostgreSQL + Alembic | dedicated `helixmind` database/schema |
| Async work | Redis + RQ | `helixmind-research`, Redis `127.0.0.1:6381` |
| Literature | NCBI E-utilities; Europe PMC REST | official public APIs; source metadata stored |
| Orchestration | OmegaClaw Core + PeTTa | private, constrained local proof runtime |
| Reasoning | MeTTa NAL/PLN | source-grounded proof verified |

Read the [infrastructure boundary](./docs/INFRASTRUCTURE.md) before deploying
on shared infrastructure.

## Literature pipeline

HelixMind uses official sources, never a language model, to retrieve papers:

1. PubMed: NCBI ESearch identifies PMIDs; EFetch returns record XML.
2. Europe PMC: the REST search endpoint returns core metadata.
3. Records are normalized into title, abstract, authors, publication date,
   DOI, URL, source metadata, and the exact source query.
4. Canonical PMID and DOI identities prevent duplicate paper records.
5. `investigation_papers` preserves paper-to-investigation provenance.

The flagship CRISPR/sickle-cell query is deliberately specific:

```text
PubMed:     ("sickle cell disease"[Title/Abstract]) AND (CRISPR[Title/Abstract] OR "gene editing"[Title/Abstract])
Europe PMC: (TITLE_ABS:"sickle cell disease") AND (TITLE_ABS:CRISPR OR TITLE_ABS:"gene editing")
```

See [the complete literature pipeline](./docs/LITERATURE_PIPELINE.md).

## OmegaClaw and MeTTa

OmegaClaw is the planned research orchestrator; MeTTa is the structured
knowledge and reasoning substrate. The repository includes a constrained proof
harness that uses OmegaClaw Core's provider/plugin mechanism, a one-shot local
channel, and a hard filesystem policy. It permits only a fixed,
source-grounded MeTTa operation—not shell, filesystem, web, or remote-channel
capabilities.

```text
HBB → HbSVariant                     (stv 1.0, 0.95)
HbSVariant → SickleCellDisease       (stv 1.0, 0.90)
────────────────────────────────────────────────────
HBB → SickleCellDisease              (stv 1.0, 0.855)
```

Provider order is Gemini `gemini-2.5-flash`, then Groq
`openai/gpt-oss-20b`. The configured Gemini model currently returns HTTP 404
for the configured account, so the verified proof used the Groq fallback. No
provider key is committed. See [OmegaClaw runtime notes](./docs/OMEGACLAW_RUNTIME.md).

## API

The local API prefix is `/api/v1`.

| Endpoint | Description |
| --- | --- |
| `GET /health` | Checks API and PostgreSQL readiness |
| `POST /investigations` | Creates and queues an investigation |
| `GET /investigations/{id}` | Reads investigation status |
| `GET /investigations/{id}/events` | Returns the traceable event stream |
| `GET /investigations/{id}/papers` | Returns papers linked to the investigation |

```bash
curl --json '{
  "question": "Investigate whether CRISPR-based genetic intervention represents a scientifically supported therapeutic strategy for sickle-cell disease."
}' http://127.0.0.1:8401/api/v1/investigations
```

The request returns immediately as `queued`; the worker performs retrieval
asynchronously.

## Local development

### Prerequisites

- Node.js 20+
- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Dedicated, non-production database and Redis instances

### Frontend

```bash
npm install
npm run dev
```

### Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

cd backend
PYTHONPATH=./ ../.venv/bin/alembic -c alembic.ini upgrade head
PYTHONPATH=./ ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8401
```

Run the worker in another terminal after configuring an isolated Redis URL:

```bash
cd backend
PYTHONPATH=./ ../.venv/bin/rq worker --url redis://127.0.0.1:6381/0 helixmind-research
```

Run tests:

```bash
PYTHONPATH=backend .venv/bin/pytest -q -p no:cacheprovider backend/tests
```

The optional OmegaClaw/PeTTa/MeTTa runtime is separate from FastAPI. Its
private dependencies are listed in
[`backend/omegaclaw/requirements.txt`](./backend/omegaclaw/requirements.txt).
Never commit provider keys.

## Repository guide

```text
app/                    Next.js workstation
backend/app/            FastAPI API, models, queue worker, literature client
backend/migrations/     Alembic migrations
backend/omegaclaw/      constrained provider and MeTTa proof configuration
backend/reasoning/      source-grounded MeTTa programs
backend/tests/          API, database, literature, and reasoning tests
deploy/                 isolated service and Redis templates
docs/                   architecture, infrastructure, and pipeline records
```

## Roadmap

- [x] Isolated API, PostgreSQL, Redis, and worker foundation
- [x] Real PubMed and Europe PMC ingestion with provenance
- [x] Constrained OmegaClaw → provider → MeTTa/NAL proof
- [ ] OmegaClaw research-plan integration into worker jobs
- [ ] Evidence extraction and supporting/contradictory assessment
- [ ] MeTTa knowledge updates from retrieved evidence
- [ ] Hypotheses, gaps, contradiction detection, and synthesis
- [ ] Live workspace, graph, and MeTTa transparency in Next.js
- [ ] Obsidian-compatible investigation export
- [ ] Nginx, TLS, and Vercel API configuration after local end-to-end validation

## Contributing

Contributions are welcome. For substantial changes, open an issue first; keep
secrets out of Git, add or update tests, and preserve provenance for every
scientific assertion. Do not present confidence values as clinical
probabilities.

## License

HelixMind is open source under the [MIT License](./LICENSE).
