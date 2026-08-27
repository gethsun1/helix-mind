# Contributing to HelixMind

HelixMind is an open-source scientific research workstation. Its goal is to
make literature retrieval, provenance, structured knowledge, and reasoning
inspectable. It welcomes contributors from MeTTa/OmegaClaw, scientific data,
backend, frontend, and research-software communities.

## Architecture and setup

The Next.js workstation runs on Vercel and calls FastAPI through its backend
proxy. NextAuth handles Google identity and persistent JWT sessions. FastAPI
synchronizes identity to PostgreSQL, authorizes requests, creates
owner-scoped investigations, and queues work in Redis/RQ. The worker runs
OmegaClaw planning and PubMed/Europe PMC retrieval. A separate constrained
OmegaClaw/PeTTa/MeTTa runtime proves NAL/PLN behavior; it is not yet the full
autonomous research layer.

Read the [README](./README.md), [literature pipeline](./docs/LITERATURE_PIPELINE.md),
[runtime notes](./docs/OMEGACLAW_RUNTIME.md), [infrastructure boundary](./docs/INFRASTRUCTURE.md),
and [ERN-AI proposal](./docs/ERN_AI_INTEGRATION.md) first.

Use Node.js 20+, Python 3.12+, PostgreSQL, and Redis with dedicated
non-production resources:

```bash
npm install
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
PYTHONPATH=. ../.venv/bin/alembic -c alembic.ini upgrade head
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8401
PYTHONPATH=. ../.venv/bin/rq worker --url redis://127.0.0.1:6381/0 helixmind-research
```

Run the frontend with `npm run dev`. Run backend tests from `backend/` with
`PYTHONPATH=.`. The optional OmegaClaw proof runtime has separate dependencies.

## Tests and change boundaries

From the repository root:

```bash
npm run build
PYTHONPATH=backend .venv/bin/pytest -q -p no:cacheprovider backend/tests
git diff --check
```

Tests cover authentication and ownership, database behavior, queue lifecycle,
literature normalization/deduplication/provenance, knowledge extraction,
graph isolation, and OmegaClaw/MeTTa proof contracts. Add regression tests with
behavior changes. Documentation-only changes do not require production service
restarts.

- **Frontend:** keep pages owner-aware, show API failures, and label planned
  graph/reasoning features as planned until backed by an API.
- **Backend/API:** keep authorization in server dependencies and queries; never
  accept client roles or investigation ownership as authority.
- **Migrations:** add one focused Alembic revision, test upgrade/downgrade, and
  use an isolated database. Never reset production data in a feature PR.
- **Worker:** preserve idempotence, explicit status/events, controlled failure
  categories, and tenant scope.
- **Literature:** normalize real records, retain identifiers and exact queries,
  deduplicate conservatively, and keep partial-source failures visible.
- **OmegaClaw/MeTTa:** keep capabilities constrained, facts inspectable, and
  source links explicit. A proof is not a production scientific claim.
- **Reasoning and export:** preserve support, contradiction, uncertainty,
  derivation traces, identifiers, timestamps, and provenance.
- **Research artifacts:** generate Markdown, structured reports, and Obsidian
  vaults only from immutable snapshot manifests. Keep output deterministic,
  owner-scoped, privately stored, digest-checked, and explicit about missing
  identifiers and uncertainty. Do not add public publishing or sharing as an
  export side effect.
- **Knowledge layer:** extend the existing Entity/Claim/Evidence/Relationship
  chain; keep every graph fact linked to a paper and exact evidence location.
  Prefer high-precision deterministic extraction over unsupported recall.
- **MeTTa:** treat PostgreSQL as canonical and MeTTa as a validated projection;
  use the existing private runtime and retain provenance IDs in every fact.
- **ERN-AI:** stop at the stored knowledge-event boundary. Do not add event
  significance, confidence decay, or autonomous reasoning in Phase 3D work.

## Scientific and security principles

1. Literature is the evidence source of truth.
2. LLM output is not automatically evidence.
3. Every scientific claim must preserve provenance.
4. Confidence is not clinical probability.
5. Contradictory evidence must remain visible.
6. Retrieved papers and metadata must never be fabricated.
7. MeTTa facts must be traceable to source evidence.
8. Reasoning should be inspectable and replayable where practical.
9. Medical output remains research information, not medical advice.
10. Never commit provider keys, production secrets, or infrastructure secrets.

Server-side authorization is authoritative. Preserve user isolation, OAuth
boundaries, server-side credentials, and fail-closed behavior.

## Workstreams and extension points

Use a focused workstream and state architectural impact in the PR:

- core research engine: investigations, orchestration, persistence
- OmegaClaw/MeTTa: orchestration, representation, NAL/PLN rules
- ERN-AI: event significance, frequency/strength, confidence, state signals
- literature: PubMed, Europe PMC, future sources, deduplication, provenance
- knowledge: entities, relationships, knowledge/evidence graphs
- scientific reasoning: support, contradiction, hypotheses, gaps, confidence
- frontend: workstation, visualizations, investigation UX, transparency
- export: Obsidian, Markdown, structured research reports from snapshots
- testing: scientific correctness, provenance, integration, regression

To add a reasoning component, define its input/output contract, provenance,
uncertainty semantics, failure behavior, and tests before wiring it into the
worker. To add a literature source, implement normalization and identifier
rules behind the pipeline and test duplicates and partial failures. Model
changes require a migration, rollback reasoning, fixtures, and an impact note.
Experimental integrations should begin as an adapter or proposal, not a hard
dependency.

Phase 4B artifacts are queued through the HelixMind worker and stored beneath
the private `HELIXMIND_ARTIFACT_ROOT`; the storage directory must never be
served as a public web directory. Phase 4C workstation filters must remain
server-backed or explicitly bounded to a selected snapshot.

## Branches, commits, and pull requests

Do not commit directly to `main`. Suggested branches include:

```text
feature/ern-ai-event-layer
feature/metta-knowledge-graph
feature/pubmed-expansion
feature/obsidian-export
feature/reasoning-contradictions
feature/mobile-ui
```

Prefer Conventional Commit-style messages such as
`feat: persist evidence provenance` or `test: cover partial source failure`.
Every substantial PR should have focused scope, tests, provenance review,
architectural impact, and no unrelated refactoring. Explain what is verified,
experimental, and unresolved. Open an issue or proposal before a cross-cutting
integration.
