# M4 Literature Intelligence 2.0 — Final Verification Report

Date: 2026-09-29
Branch: `feat/persistent-research-memory-track-03`
M3 starting commit: `f090dc6` (`feat: complete M3 knowledge graph verification`)

## 1. Executive Summary

M4 extends the existing PubMed and Europe PMC pipeline with investigation
literature profiles, evidence contribution paths, deterministic relevance,
coverage, snapshot comparison, and graph/publication navigation. It retains
the existing implementation and adds no parallel literature subsystem.

The isolated real CRISPR–sickle-cell workflow completed through retrieval,
evidence extraction, graph/reasoning, and immutable snapshots. The full
backend suite, frontend build, and Chromium workflow passed. The final
acceptance audit re-ran the backend suite and Chromium workflow and inspected
the retained isolated workflow and snapshots. M4 is accepted and complete.
The dependency audit still reports high/critical findings that require a Next
major upgrade; no deployment was attempted.

## 2. PostgreSQL Environment Verification

- `pg_isready -h /var/run/postgresql -p 5433`: **accepting connections**.
- `psql` as the `helixmind` OS/database user connected to `helixmind_test`.
- Database: `helixmind_test`; user: `helixmind`.
- Alembic revision: `8a2c4e6f0b11`.
- Runtime and tests explicitly used `postgresql+psycopg:///helixmind_test?host=/var/run/postgresql&port=5433`.
- No production database was used or migrated.

The default port/socket failure from the earlier attempt was an invocation
mismatch. The documented cluster and peer-authenticated OS user recovered the
known M3 test environment.

## 3. M3 Baseline

The starting worktree was clean on `feat/persistent-research-memory-track-03`
at `f090dc6`. M3 documentation, graph ownership checks, and the existing
snapshot implementation were reviewed. The M3 test baseline passed **61
tests** on the recovered isolated database.

## 4. Existing Literature Architecture Audit

PubMed ESearch/EFetch and Europe PMC REST retrieval, query construction,
normalization, canonical `Paper` persistence, `InvestigationPaper` source
associations, `ResearchSearch` provenance, and evidence extraction were
preserved. PMID, DOI, and PMCID identity precede the existing conservative
normalized title/first-author/year fallback. Existing investigation-scoped
claims, evidence, graph records, propositions, hypotheses, runs, and immutable
snapshot manifests supply M4 data.

The system still uses only PubMed and Europe PMC. No arbitrary web search,
semantic retrieval, vector database, LLM evidence path, or graph database was
added.

## 5. M4 Architecture

M4 derives intelligence from the canonical PostgreSQL models. Global
publication metadata is returned only where `InvestigationPaper` associates
the publication with the requested investigation. Scientific contributions
additionally require links through that investigation's claims, evidence, and
graph/reasoning records. No migration or new persistence model was needed.

## 6. Publication Identity / Deduplication

Identifier normalization covers DOI URL/prefix variants and PMID/PMCID
prefixes. Canonical deduplication preserves the existing PMID → DOI → PMCID →
provider ID → conservative title/author/year order. M4 reports matching
identifiers and exact normalized-title matches as advisory candidates only;
it does not merge records. Synthetic tests cover identifier matches and
distinct authors under the fallback key.

Real workflow result: 20 canonical publications; zero pipeline duplicates
removed and zero remaining M4 duplicate candidates. Source metadata counts 11
PubMed and 10 Europe PMC source records; provider records can overlap on a
canonical publication.

## 7. Evidence Contribution

Publication detail derives evidence, claims, entities, relationships,
propositions, and hypotheses from scoped persisted records. Evidence includes
source location, exact source span, and polarity when present. Relationship
records identify the evidence IDs supporting them. Missing source metadata is
not fabricated.

## 8. Literature Relevance

`literature-relevance-v1` uses retrieval rank (0.15), evidence contribution
(0.30), evidence-linked entity overlap (0.20), proposition linkage (0.20),
and hypothesis linkage (0.15). Counts saturate at three; rank is clamped from
`1 - (rank - 1) / 20`; missing/invalid rank contributes zero. The API returns
normalized inputs, weights, score, and formula version. Determinism and
missing-rank behavior have focused tests. The signal does not mutate evidence
confidence or imply scientific validity. One real publication returned a
score of `1.0` from its disclosed inputs.

## 9. Literature Landscape

The API separately reports retrieved and unique publications, evidence-bearing
publications, entity-linked publications, relationship-linked publications,
proposition-linked publications, hypothesis-linked publications, provider
source-record distribution, publication dates, and persisted evidence
polarity.

## 10. Evidence Coverage / Limited Support

Coverage returns per-entity, per-proposition, and per-hypothesis linked
publication counts. Labels say “limited retrieved evidence” or “multiple
retrieved publications”; they do not infer evidence of absence. The real run
returned coverage for 101 entities, 11 propositions, and 11 hypotheses. The
model does not invent topics absent from persisted evidence/graph records.

## 11. Run-to-Run Literature Comparison

The comparison API checks both snapshots against the requested investigation,
then compares their immutable manifests. It reports added, removed, and
retained publications and per-publication evidence, claim, entity,
relationship, proposition, and hypothesis contributions added, removed, or
changed. Stable record IDs are compared using frozen snapshot record digests.
Historical records are never rewritten.

Real comparison: 20 retained publications, zero added, zero removed, zero
contribution changes. Synthetic snapshot tests verify added and changed
evidence, claims, and hypotheses. Cross-investigation snapshots return 404.

## 12. Publication → Graph Traversal

The investigation literature explorer opens scoped publication detail with
evidence and connected entity, relationship, proposition, and hypothesis
records. Graph links retain investigation scope and evidence provenance.

## 13. Graph → Publication Traversal

Entity, relationship, proposition, and hypothesis support endpoints resolve
publications through investigation-scoped claims and persisted evidence. The
Knowledge Graph inspector links evidence-backed papers to their investigation
publication detail; proposition and hypothesis nodes link to supporting
publications. Missing support is presented as limited publication support.

## 14. API Verification

Runtime checks against the real test-database workflow returned HTTP 200 for
intelligence, publication detail, and entity/relationship/proposition/
hypothesis publication traversal. The real snapshot comparison returned HTTP
200. Requests for an out-of-scope publication or snapshot were rejected.

## 15. Isolation Verification

Expanded synthetic integration coverage tests same-owner/different-investigation
and cross-owner access. The same globally canonical paper is associated with
two investigations and carries different persisted evidence in each. The
publication metadata is visible to both associated investigations, while each
publication detail, evidence path, graph traversal, and snapshot exposes only
its own investigation's contribution. Same-owner cross-investigation and
cross-owner requests to literature and graph endpoints are denied.

## 16. Reproducibility

Two real runs and snapshots were retained. Both snapshot manifest digests
verified, and the digests remained unchanged after comparison. All 162 real
evidence source spans matched their exact abstract substring. Relevance is
derived from canonical inputs and its formula version/inputs are returned.

## 17. Playwright / Chromium Verification

**PASS.** The repository config uses Chromium at `/snap/bin/chromium`; Chromium
153 and Playwright 1.63.0 were available after installing the declared test
dependency. The browser test used authenticated real API data from
`helixmind_test` and verified the investigation landscape, publication detail,
evidence contribution, graph navigation in both directions, limited-support
content, and snapshot comparison. Result: **1 passed**.

## 18. Frontend Verification

**PASS.** `npm run build` succeeded on Next.js 14.2.35. The build emitted two
existing Autoprefixer compatibility warnings in `app/globals.css` for `start`
and `end` flex alignment values; they did not prevent compilation or build.

## 19. Real CRISPR / Sickle-Cell Workflow

- Investigation ID: `12565bbb-4cd0-4078-bbf7-9d950545e068`
- Owner ID in the isolated fixture: `00000000-0000-0000-0000-000000000001`
- Run 1: `c82f56c6-e0a5-45c6-aa30-e6d925366d7e`
- Snapshot 1: `21c394df-b013-41c1-9c53-54910f24d454`
- Run 2: `5d317ed6-45f7-43d8-b6bc-cb116a478470`
- Snapshot 2: `fccb6444-7aed-4ddb-b900-c072d6667cdb`
- Both runs completed; PubMed and Europe PMC reported no source failures.
- The stored run metadata records `model: none` and
  `orchestrator: deterministic_fallback`; no LLM-generated literature
  evidence entered this workflow.
- Each run retained 20 canonical publications. The second run reused the
  recent persisted source searches to provide a reproducible comparison.
- First run persisted 162 claims/evidence records, 138 graph entities, and 13
  relationships; 15 publications carried evidence and eight linked to
  relationships, propositions, and hypotheses.
- Duplicate candidates: zero. Source spans: 162/162 exact matches. Snapshot
  digests: valid. Graph traversal: all four graph kinds returned linked
  evidence-backed publications.
- Snapshot comparison: 20 retained, zero added/removed, zero changed
  contributions.

No publications or graph facts were fabricated.

## 20. Backend Test Results

**PASS.** Full backend suite: **64 passed**, one upstream Starlette deprecation
warning. Focused M4, relevance, identity, snapshot-diff, and isolation tests
also passed. Tests ran as OS user `helixmind` against port 5433 and
`helixmind_test`.

## 21. Frontend Build

**PASS.** Next.js production build completed, including the nested investigation
literature and graph-support routes.

## 22. `git diff --check`

**PASS.** No whitespace errors.

## 23. Files Modified / Created

- Backend: `backend/app/literature_intelligence.py`,
  `backend/app/routes/literature_intelligence.py`, `backend/app/main.py`.
- Backend tests: `backend/tests/test_literature.py`,
  `backend/tests/test_knowledge_isolation.py`.
- Frontend: investigation literature explorer and publication/graph detail
  routes under `app/investigations/[id]/literature/`,
  `app/investigations/[id]/page.tsx`, and `app/knowledge/page.tsx`.
- Browser verification: `e2e/literature-intelligence.spec.ts` and the existing
  `playwright.config.ts`.
- Docs: `docs/LITERATURE_INTELLIGENCE_2.0.md` and this report.
- Dependencies: `package.json`, `package-lock.json`.

## 24. Database Changes

None. No migrations were added or run.

## 25. Deployment Impact

No deployment, commit, or push was performed. No production database was
modified. Do not deploy until the dependency security finding below is
resolved.

## 26. Security Review

Investigation ownership checks precede M4 reads; publication exposure requires
an investigation association; contribution queries scope claims/evidence and
graph records to that investigation. Synthetic tests verify global paper
reuse does not expose another investigation's contribution.

The dependency audit prompted same-major updates to Next.js 14.2.35 and
NextAuth 4.24.15. `npm audit` still reports one critical Next.js and one high
PostCSS finding. The audit identifies a complete remediation at Next.js
16.3.7, which is a major upgrade and is outside this M4 implementation change.
This is a **deployment security hold**, not an M4 literature feature failure.

## 27. Remaining Limitations

- Literature coverage describes persisted evidence/graph contribution; it
  does not infer topics for retrieved publications that have no persisted
  graph/evidence representation.
- Real run-to-run comparison had no contribution changes; synthetic snapshot
  fixtures exercised changed-record and add/remove behavior.
- High/critical frontend dependency advisories remain until a separately
  reviewed Next major upgrade.

## 28. M4 Acceptance Criteria

- [x] Existing literature architecture audited — **PASS**
- [x] Existing PubMed/Europe PMC pipeline preserved — **PASS**
- [x] Deterministic publication identity verified — **PASS**
- [x] Conservative deduplication verified — **PASS**
- [x] Investigation-scoped literature intelligence implemented — **PASS**
- [x] Publication evidence contribution implemented — **PASS**
- [x] `literature-relevance-v1` deterministic and auditable — **PASS**
- [x] Literature landscape implemented — **PASS**
- [x] Evidence coverage / limited-support analysis implemented — **PASS**
- [x] Run-to-run literature contribution comparison implemented — **PASS**
- [x] Publication → graph traversal implemented — **PASS**
- [x] Graph → publication traversal implemented — **PASS**
- [x] Provenance preserved — **PASS**
- [x] Same-owner cross-investigation isolation passes — **PASS**
- [x] Cross-owner isolation passes — **PASS**
- [x] Real CRISPR/sickle-cell workflow passes — **PASS**
- [x] Backend tests pass — **PASS**
- [x] Frontend build passes — **PASS**
- [x] Playwright/Chromium verification attempted and passes — **PASS**
- [x] Interactive literature explorer verified — **PASS**
- [x] `git diff --check` passes — **PASS**
- [x] No production migration — **PASS**
- [x] No deployment — **PASS**
- [x] No prohibited architecture introduced — **PASS**

## 29. M5 Recommendation

Do not start M5 in this change. First review/close M4 and separately resolve
the frontend dependency security hold before any deployment.

## 30. Final M4 Status

**M4 ACCEPTED / COMPLETE.** Final acceptance re-run: backend suite **64
passed, zero failures, zero skips**, with one upstream Starlette deprecation
warning; the Chromium M4 smoke test **1 passed** against the isolated real
workflow. Retained workflow and snapshot records were independently checked:
both provider searches succeeded, 162/162 source spans matched, both snapshot
digests validated, and the comparison reproduced 20 retained publications
with zero additions, removals, or contribution changes. The changes remain
uncommitted on `feat/persistent-research-memory-track-03` at
`f090dc6`. **Deployment remains blocked** by one critical Next.js finding
and one high PostCSS finding; npm audit reports the complete fix as Next.js
`16.3.7`, a major upgrade for separate security maintenance. No M5 work was
started.
