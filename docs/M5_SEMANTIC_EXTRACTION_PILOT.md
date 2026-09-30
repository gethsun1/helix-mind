# M5 Semantic Extraction Pilot

## Status

**ACCEPTED** after live source-grounded extraction in isolated `helixmind_test`.
Groq through the Cloudflare Worker returned a valid completion using
`openai/gpt-oss-120b`; deterministic validation accepted one candidate and
projected its relationship. The source snapshot remained unchanged, and a new
post-projection snapshot has a valid digest. Earlier bounded live attempts that
produced rejected candidates and provider timeouts remain recorded as failed or
rejected audit history in the test database.

## Architecture

The existing deterministic literature/evidence extractor remains unchanged.
The M5 service reads only persisted abstract-backed `Evidence` records joined
to their `Paper`, investigation association, and source `Claim`. Model output
is stored in the investigation-scoped `SemanticExtraction` table. It is not
stored as `Evidence` or `Claim` and cannot overwrite canonical publication
records.

The table is required because existing evidence and claims represent the
deterministic source pipeline; they cannot safely represent rejected model
output, model provenance, or extraction validation state. It is the only new
store and remains in the canonical HelixMind PostgreSQL database. The
`semantic_extractions` migration is a focused extension; no vector index,
separate literature database, or graph store is added.

The existing `InferenceRouter` supplies the configured provider/model. The
default order is Groq, ASI Cloud, then Gemini. Transient retries are bounded;
rate limit, permission, authentication, and missing-configuration failures can
fall through to the next provider. Invalid requests do not trigger fallback.
Groq uses an external OpenAI-compatible Cloudflare Worker, with IPv4 outbound
transport for this VPS. An extraction creates a child `InvestigationRun` whose
`parent_run_id` references the completed source run. Each call processes a
deterministic evidence prefix capped at 20 rows by default (configurable up to
100); exact selected evidence/publication IDs and the cap are persisted in the
run input manifest. Provider metadata records provider, model, version, output
hash, candidate IDs, evidence count, and validation counts. Provider
generation can vary between requests.

Configure provider endpoints, model names, keys, routing order, and the
evidence cap with `GROQ_API_BASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`,
`ASI_CLOUD_BASE_URL`, `ASI_CLOUD_API_KEY` (and numbered key variables),
`ASI_CLOUD_CHAT_MODEL`, `GEMINI_BASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`OMEGACLAW_PROVIDER_ORDER`, and `SEMANTIC_EXTRACTION_MAX_EVIDENCE`. Keep all
credentials server-side; this repository documents variable names only.
Execution requires the source run's immutable snapshot. Evidence IDs,
publication abstracts, and available entity references are bounded to records
in that snapshot, whose digest is verified before use, so later investigation
updates cannot silently alter a re-run's input set.

## Candidate contract and provenance

The model returns a JSON object containing a `relations` array. Each relation
must have exactly `evidence_id`, `subject`, `subject_type`, `predicate`,
`object`, `object_type`, `source_span`, and `semantic_type`.

Supported semantic types are `INTERVENTION`, `TARGET`, `CONDITION`,
`PHENOTYPE`, `POPULATION`, `MECHANISM`, `EXPERIMENTAL_CONTEXT`, and
`EVIDENCE_RELATION`. Entity references must use existing graph entity types
and resolve to entities already attached to claims in the same investigation.
Relations are limited to `SUPPORTS`, `CONTRADICTS`, `ASSOCIATED_WITH`,
`CAUSES`, `INHIBITS`, `ACTIVATES`, `MODIFIES`, `MEASURED_IN`, and
`OBSERVED_IN`.

Each persisted row identifies the investigation, canonical publication,
source evidence, source claim when available, source run, extraction run,
version, provider/model, source span and locator, normalized candidate hash,
validation state, rejection reasons, and projected relationship if any.
Raw candidate fields are retained for audit. Malformed model output is marked
rejected; model credentials and prompt secrets are never stored.

## Validation and graph boundary

Validation is deterministic and checks the response shape, vocabulary,
publication/evidence/claim ownership, investigation publication association,
exact source-span containment in both stored evidence text and the publication
abstract, source offsets, explicit subject/object mentions, allowed entity
references, explicit lexical predicate cues, and self-relations. Repeated
identical normalized candidates for the same source run are deduplicated by a
SHA-256 hash. Candidate list output is ordered deterministically by evidence
identity and source offsets.

Only a candidate with `validation_status=VALID` is projected. Projection
creates an investigation-scoped existing `Relationship` linked through
`RelationshipClaim` to the existing source claim, and therefore through its
existing `ClaimEvidence` to source evidence. It creates no evidence, claims,
entities, or propositions. Relationship confidence and strength are stored as
zero to indicate that M5 did not assess either quantity. The relationship
metadata explicitly says confidence is not assessed. Candidate output never
enters the authoritative graph before validation.

Conflicting source relations remain separate source-linked records; the
service does not choose which publication is correct. Existing snapshots are
not modified. A new ordinary immutable snapshot after projection captures the
graph relationship through the existing snapshot mechanism.

## Confidence and reproducibility

The pilot does not request or persist model confidence. `validation_status`
means only that the candidate passed structural, provenance, and vocabulary
checks. It is not a measure of scientific truth, causal certainty, clinical
probability, treatment efficacy, or consensus.

Source identity and offsets are preserved from stored evidence. Validation,
normalization, sorted output, and candidate hashing are deterministic for the
same stored inputs and normalized model candidate. Provider generation is not
claimed to be deterministic; provider/model and a digest of the returned
generation are recorded.

## API and UI

- `GET /api/v1/investigations/{id}/literature/semantic-extractions`
- `GET /api/v1/investigations/{id}/literature/semantic-extractions/{extraction_id}`
- `POST /api/v1/investigations/{id}/literature/semantic-extractions` with
  `source_run_id` for a completed source run

All endpoints scope the investigation to its owner or the existing ADMIN
role. Extraction additionally requires a completed source run belonging to
that investigation with an immutable snapshot. The literature view offers a completed-run selector and a
focused candidate panel with publication/evidence/claim identity, exact span,
validation errors, model/provider/version, run/hash, and graph projection.

## Limitations and failure modes

- The current API trigger is synchronous; provider delays can outlast a browser
  request. A queue-backed execution may be needed after the pilot proves useful.
- One provider completion is deliberately limited to a deterministic evidence
  subset. Additional coverage uses further bounded extraction runs.
- Exact lexical relation checks favor precision and will reject valid
  paraphrases or non-English source statements.
- Entity references must already exist in deterministic graph output; M5 does
  not create or synonym-merge entities.
- Source offsets are abstract offsets. Full-text or section extraction is not
  included.
- Candidate audit rows remain in the investigation-scoped extraction table;
  accepted graph links are captured in an ordinary post-projection snapshot.

## Security and privacy

Provider calls contain only persisted abstract evidence, IDs, and linked
claims. The prompt tells the model to treat source text as untrusted data and
not instructions. The UI/API do not expose credentials. Candidate reads and
run triggers follow the existing owner/ADMIN investigation scope, preventing
cross-owner and cross-investigation disclosure. Canonical publications can
remain global, but extraction records are investigation scoped. No production
database migration or deployment was performed.

## Verification record

- Worker smoke from the VPS returned HTTP 200, a valid chat completion,
  `openai/gpt-oss-120b`, and usage metadata. The backend `httpx` transport also
  passed through the Worker after selecting IPv4 for this host.
- Investigation `12565bbb-4cd0-4078-bbf7-9d950545e068`; source run
  `5d317ed6-45f7-43d8-b6bc-cb116a478470`; accepted extraction run
  `7e59e47a-2f35-49f5-975a-01f55da03d90`.
- Literature scope: 20 investigation publications, 162 evidence rows and 162
  claims. The bounded M5 run processed 20 evidence rows from 3 publications;
  all selected evidence/publication IDs are persisted in its input manifest.
- Across completed live extraction attempts: 4 candidates, 1 valid and 3
  rejected. The accepted run produced 1 valid candidate, 0 rejected, and 1
  projected relationship. Rejections included unknown entities, self-relations,
  and relation cues not explicit in the source span.
- The accepted candidate links publication, evidence, claim, investigation,
  exact abstract span/locator, provider/model, extraction version, and candidate
  hash. Repeated validation and hash recalculation matched.
- The projected relationship remains investigation-scoped and linked to its
  source claim/evidence. It appears in post-projection snapshot
  `2a2241a6-f992-4628-8b96-87671f98daa7`; its digest validates. The frozen M4
  source snapshot digest remains valid and unchanged.
- Isolation checks found no semantic rows outside their owning investigation.
  A publication reused across investigations had no extraction-state leak;
  every candidate matched its investigation/publication association. Cross-owner
  API scope is covered by backend tests.
- Invalid source span, missing claim provenance, invalid relation, unknown
  entity, self-relation, and duplicate candidates are covered by validation
  tests. Invalid candidates cannot project.
- Full backend suite on `helixmind_test`: **75 passed**. Next.js production
  build: **passed**. Chromium M5/literature/graph smoke: **1 passed**, including
  the live candidate, graph relationship, source navigation, empty state,
  loading state, and provider failure state.
- Provider tests cover URL/model configuration, success, 403/429, bounded
  retries, missing Groq/ASI keys, Groq→ASI and ASI→Gemini fallback, unavailable
  providers, metadata, and secret redaction.
- Provider credentials remain outside Git; the repository secret-pattern scan
  and `git diff --check` pass. Production services and research data were not
  deployed or modified.

The pilot is accepted within its bounded evidence-slice scope. The Cloudflare
Worker is external infrastructure; keep its endpoint configurable and all
provider credentials in server environment variables only.
