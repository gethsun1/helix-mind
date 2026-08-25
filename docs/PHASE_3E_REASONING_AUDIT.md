# Phase 3E audit and reasoning evaluation gate

Audit date: 2026-08-25
Repository: `gethsun1/helix-mind`
Audit baseline: commit `742abb8` before the audit-only trace/test changes

This is a fresh repository, database, service, and test audit. It does not
authorize Phase 4 implementation, ERN-AI deployment, semantic contradiction
detection, or a change to the Phase 3E confidence formula.

## VERIFIED

### Verified architecture and runtime path

The implemented path is:

```text
owner-scoped research question
  -> server-side investigation and structured plan
  -> RQ worker
  -> PubMed / Europe PMC source records
  -> canonical paper and investigation-paper provenance
  -> exact abstract claims and evidence spans
  -> deterministic entities and explicit relationships
  -> structured propositions and evidence polarity
  -> deterministic hypothesis, contradiction, gap, and trace records
  -> MeTTa rendering and private PeTTa syntax validation
```

The PostgreSQL records are authoritative. Provider calls can plan or support
bounded extraction, but the Phase 3E aggregation path reads persisted source
evidence and does not ask an LLM to assign a truth value or confidence.

The live flagship investigation was checked by ID without exposing secrets:

| Record or check | Result |
| --- | ---: |
| Linked retrieved papers | 18 |
| Claims | 192 |
| Evidence records | 192 |
| Structured propositions | 22 |
| Hypotheses and inferences | 22 each |
| Open knowledge gaps | 6 |
| Contradiction records | 0 |
| Evidence missing paper, span, or location | 0 |
| Proposition, hypothesis, or gap provenance field null | 0 |

The 192 claims/evidence records are intentionally not equivalent to 192
propositions. Nineteen evidence records are linked to propositions; 173 remain
fully source-linked claims/evidence without a supported deterministic
subject-predicate-object relationship. They are retained, not converted into
invented propositions. This is the main current extraction coverage gap.

Runtime checks passed for the HelixMind API health endpoint, Redis on the
HelixMind loopback port, PostgreSQL connectivity, and Alembic at
`b8d9e0f1g2h3` (head). The HelixMind API, worker, Redis, and PostgreSQL
services were active during the audit. No unrelated service was changed.

### Provenance audit

The supported chain is represented by foreign keys and source metadata:

```text
Investigation
  -> InvestigationPaper -> Paper/source identity
  -> Claim/paper_id -> ClaimEvidence -> Evidence/paper_id/source_span
  -> Evidence/proposition_id -> Proposition/proposition_key
  -> Hypothesis/proposition_id -> Inference/hypothesis_id
  -> KnowledgeGap/proposition_id/hypothesis_id
  -> Contradiction/proposition_id/supporting_evidence_id/
     contradictory_evidence_id
```

Evidence exposes the source location, exact abstract span, extraction method,
polarity, strength signal, confidence signal, paper ID, and proposition ID.
Reasoning traces retain the IDs of all evidence considered, support and
opposition lists, applied relationships, rule name, result, confidence, and
uncertainty metadata. The trace relationship lookup was corrected during this
audit; it now matches the proposition to the persisted subject and object
entities instead of comparing UUIDs with normalized names.

The remaining provenance limitation is aggregation granularity. A proposition
is created with the first source claim's provenance and later evidence remains
source-linked at the Evidence level. Proposition, hypothesis, and gap
provenance therefore do not yet provide a complete distinct-source roll-up.
The complete source path is still recoverable through evidence IDs and the
trace, but downstream consumers must follow those IDs rather than treat the
top-level JSON provenance object as an exhaustive bibliography.

### Confidence audit

The current formula is deterministic and bounded by a final clamp and round:

```text
confidence = clamp(
  0.45 * polarity_balance * quality * (0.5 + 0.5 * independence)
  + 0.25 * independence
  + 0.20 * mean_extraction_confidence
  + 0.10 * provenance_completeness
)
```

Where `quality` is the mean of `clamp(strength * extraction_confidence)` for
supporting and contradictory evidence, `independence` is
`min(distinct supporting paper IDs, 3) / 3`, and provenance completeness is
the fraction of evidence items with paper ID, source span, and source
location. Polarity balance is the supporting weighted signal divided by the
supporting plus contradictory weighted signal. Neutral and uncertain evidence
are counted in uncertainty but do not contribute to that polarity denominator.

The formula is mathematically reproducible for the same ordered set of stored
inputs and is explicitly labelled as HelixMind evidence confidence, not a
probability of truth, study quality, clinical efficacy, or clinical certainty.
The audit did not silently change it.

Risks requiring a future versioned formula or calibration study:

- Database fields do not enforce that stored strength/confidence inputs are in
  `[0, 1]`; the final output clamp hides invalid inputs rather than rejecting
  them. The arithmetic mean also consumes the raw stored confidence values.
- Repeated evidence from one paper remains multiple evidence items. Distinct
  source counting limits the independence term, but duplicated support or
  opposition can still alter the weighted balance and item-level quality.
- `source_coverage` is calculated in the current implementation but is not
  used in the formula.
- The lexical extractor treats absence of an opposing cue as support. This is
  conservative for the current bounded sentence extractor only and is not
  semantic scientific classification.
- The fixed `0.600` strength is an extraction assessment signal, not a
  measured study-quality score.

These are documented risks, not hidden formula changes. A future formula
change must carry a new formula version, fixtures, migration/interpretation
notes, and comparison results.

### Contradiction audit

The production contradiction gate is structural plus polarity-based:

1. Evidence is grouped by one investigation and one stable structured
   proposition.
2. The lexical polarity extractor labels explicit negative cues as
   `CONTRADICTS`, uncertainty cues as `UNCERTAIN`, neutral cues as `NEUTRAL`,
   and otherwise `SUPPORTS`.
3. A contradiction pair requires one supporting and one contradictory evidence
   item for that same proposition.
4. Both evidence IDs, paper IDs, source spans, type, confidence, and context
   are persisted.

This prevents unrelated claims from becoming contradictions merely because
their papers differ. It also does not infer contradiction from titles, paper
metadata, different predicates, different propositions, or a missing source
span. `DIRECT`, `CONTEXTUAL`, and `INSUFFICIENT_EVIDENCE` are explicit labels;
normal abstract evidence has a span, so the contextual helper branch is not
normally reached by the current extractor.

The system does not currently distinguish semantic, structural, lexical,
evidence-polarity, and hypothesis-level disagreement as separate production
classes. It has no semantic contradiction detector and no apparent-versus-
genuine disagreement resolver. The live zero count means no qualifying pair
was found in this corpus; it does not mean the literature has no scientific
disagreement. No manufactured contradiction was added for testing or demo
data.

### MeTTa, NAL, and Python boundary

- Python persists and aggregates the canonical database records, applies the
  explicit evidence-polarity heuristic, calculates the current formula, and
  writes the inspectable reasoning trace.
- `knowledge_metta.py` renders database entities, claims, evidence,
  propositions, polarity, hypotheses, contradictions, and gaps as MeTTa
  facts. `validate_metta_text` checks the generated representation through the
  private PeTTa runtime. This is representation validation, not production
  NAL inference.
- OmegaClaw is used for restricted planning/provider orchestration and has a
  separate constrained proof adapter. It is not allowed to write scientific
  conclusions into the evidence store.
- The genuine OmegaClaw -> PeTTa -> MeTTa -> NAL proof remains the separate
  fixed HBB/sickle-cell proof under `backend/reasoning/` and its integration
  test. It is not evidence for the live literature corpus.
- `transitive_support` is a bounded Python test/integration primitive. It is
  not evidence that the Phase 3E worker executes a general MeTTa or NAL rule
  library.

### ASI, Groq, and Gemini inference audit

The shared OpenAI-compatible adapter supports ASI, Groq, and Gemini using
server-side environment configuration. When `OMEGACLAW_PROVIDER=asi`, the
configured order is ASI -> Groq -> Gemini; the default existing order remains
Gemini -> Groq. ASI has three ordered credential slots. Keys are never sent to
the frontend or included in diagnostics/log fields; logs expose provider,
model, credential slot, latency, request ID where supplied, usage where
supplied, and safe error categories.

The adapter selects chat and embedding models from environment configuration,
supports `/models` discovery, retries timeout/connection/5xx failures with
bounded backoff, rotates credentials for authentication/rate-limit failures,
and the router records whether provider fallback occurred. Invalid requests
and unavailable models fail without needless credential rotation. Current
runtime proof documentation records Gemini model unavailability followed by a
Groq fallback; this is provider-state evidence, not a fabricated success.

The audit found two follow-up risks: exhausted network retries currently move
to the next credential slot even though credential rotation is intended for
auth/rate-limit cases, and embedding metadata does not include provider token
usage. Retry counts, rate-limit rotation, timeout/5xx exhaustion, final Gemini
fallback, model discovery, and those observability fields need broader tests.

## RISKS

- Proposition-level reasoning covers only explicit lexical relationships; the
  173 unpropositioned evidence records are not silently promoted into
  hypotheses.
- Top-level proposition/hypothesis/gap provenance is not a complete source
  roll-up when multiple papers support the same proposition.
- Confidence is an explainable evidence score, not a calibrated probability,
  and duplicate evidence can affect the score.
- Contradiction detection is intentionally non-semantic and can miss
  contextual, methodological, population, endpoint, or negation patterns.
- The separate NAL proof must not be presented as general literature
  reasoning.
- ASI provider behavior remains dependent on external model availability,
  rate limits, and gateway response shape.

## GAPS

The following are outside the completed gate and remain explicit work:

- Complete provenance roll-up across all claims/evidence feeding one
  proposition, with source-level deduplication rules.
- Versioned confidence calibration and invalid-input rejection.
- Broader deterministic extraction or a separately evaluated semantic
  extraction layer for full-text context and competing hypotheses.
- Production taxonomy for lexical, structural, semantic, evidence-polarity,
  and hypothesis disagreement.
- Full NAL/PLN rule coverage integrated with replayable source-grounded facts.
- ASI retry/observability test coverage described above.
- ERN-AI event ingestion and assessment, which is deliberately not part of
  this audit implementation.

## ERN-AI INTERFACE

This section is a design boundary only. No ERN-AI adapter, event table, scorer,
or reasoning integration was implemented.

A future upstream event envelope should be versioned and append-only:

```json
{
  "event_id": "uuid",
  "schema_version": "1.0",
  "source": {"kind": "PUBMED", "id": "source-record-id", "provider": "NCBI"},
  "timestamp": "2026-08-25T00:00:00Z",
  "type": "paper_retrieved",
  "payload_ref": {"kind": "paper", "id": "uuid"},
  "payload_digest": "sha256",
  "salience": 0.0,
  "novelty": 0.0,
  "confidence": 0.0,
  "relevance": 0.0,
  "priority": 0.0,
  "provenance": {"investigation_id": "uuid", "query": "exact query"},
  "affected_entities": [],
  "affected_propositions": [],
  "processing": {"status": "unassessed", "adapter": null, "adapter_version": null}
}
```

`payload_ref` and the digest identify persisted source data; they are not a
replacement for it. ERN-AI must be upstream of reasoning, owner-scoped, and
unable to become the source of truth. Missing or unavailable assessment must
remain explicit and must never manufacture confidence, salience, novelty,
relevance, or priority. The original source event and any assessment failure
must be replayable and retained.

## RECOMMENDED NEXT PHASE

The smallest safe next milestone is a versioned, append-only scientific-event
ingress contract with schema validation, authorization, provenance retention,
replay fixtures, and a no-op assessment sink. It should not score significance,
change confidence, write propositions, or alter the canonical reasoning path
until deterministic replay and source-retention tests pass. ERN-AI assessment,
MeTTa serialization, and NAL updates should follow as separately versioned
adapters.

## TEST RESULTS

The audit added deterministic evaluation cases for support, opposition,
insufficient evidence, competing/unrelated propositions, repeated evidence,
and confidence change across independent sources. It also added an assertion
that persisted traces include the matching relationship IDs and extended
ownership tests to all Phase 3E knowledge/reasoning endpoints. No external LLM
is used by these tests.

Final verification completed successfully:

- backend pytest with `PYTHONPATH=.` and cache disabled: **33 passed**;
- frontend `npm run build`: **exit 0**;
- API health: **ok**; Redis: **PONG**;
- PostgreSQL/Alembic: **`b8d9e0f1g2h3 (head)`**;
- HelixMind API, worker, Redis, and PostgreSQL services: **active**;
- MeTTa/proof integration: included in the passing backend suite;
- `git diff --check`: **clean**; secret-pattern scan: **no matches**.

The final audit commit is recorded in the GitHub handoff.

## GIT STATUS

Audit changes are limited to the reasoning trace lookup, deterministic tests,
the audit document, and precision updates to existing documentation. No
Phase 4/ERN-AI runtime, semantic contradiction detector, migration, secret,
or unrelated project change is included.
