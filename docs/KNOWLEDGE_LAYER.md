# Phase 3D knowledge layer

Phase 3D extends the verified literature layer into a provenance-preserving
knowledge system:

```text
Investigation → linked Paper → abstract Evidence → Claim → Entity
                                      └──────────────→ Relationship
                                      └──────────────→ MeTTa representation
```

## Implemented

- `Entity` supports canonical and normalized names, aliases, domain-neutral
  types, and source-paper metadata.
- `Claim` stores an exact source sentence, normalized text, paper,
  investigation, deterministic identity hash, extraction method, and extraction
  confidence. Extraction confidence is not scientific truth probability.
- `Evidence` records the paper, abstract source location, exact text, character
  span, retrieval metadata, and extraction timestamp.
- `ClaimEvidence` and `RelationshipClaim` preserve the many-to-many provenance
  chain.
- `Relationship` records subject/object entities, an extensible predicate,
  investigation scope, stance, and linked claims. `SUPPORTS`, `CONTRADICTS`, and
  `NEUTRAL` are representable; Phase 3D does not infer contradictions.
- The deterministic extractor uses source-provided keywords/MeSH/title terms
  and exact abstract sentences. Explicit lexical predicates are required for a
  relationship. It favors precision and rejects unsupported output.
- Extraction is idempotent by investigation/paper claim hashes and entity
  normalized identity.
- The existing worker persists knowledge after literature acquisition and emits
  knowledge events through `investigation_events`.
- Canonical records convert to MeTTa facts and are validated through the
  existing private PeTTa runtime. The database remains independent of MeTTa
  syntax.
- Owner-scoped summary, graph, entity, claim, and relationship APIs are
  available under `/api/v1/investigations/{id}/knowledge`.
- `/knowledge` provides a bounded, searchable graph with entity/relationship
  inspection and source claim visibility.

## Extraction and integrity boundary

The current implementation is deterministic and abstract-only. It does not
use Gemini or Groq for knowledge extraction. This is intentional: an LLM
adapter can be added behind the `KnowledgeExtractor` protocol later, but only
strict, evidence-linked structured output should be persisted. A model-produced
claim without a retrieved paper/evidence span must be rejected.

Missing abstracts produce no claims or evidence. No page, section, quotation,
identifier, or scientific relationship is invented. Phase 3D extraction stays
conservative; Phase 3E adds explicit proposition polarity, deterministic
evidence confidence, hypotheses, contradiction pairs, and traces without
changing source provenance.

## API

All routes require the existing authenticated bearer session and verify the
investigation owner server-side. Administrators retain existing visibility.

| Route | Purpose |
| --- | --- |
| `GET /investigations/{id}/knowledge` | Bounded summary and graph |
| `GET /investigations/{id}/knowledge/graph` | Graph nodes and edges |
| `GET /investigations/{id}/knowledge/entities` | Investigation-scoped entities |
| `GET /investigations/{id}/knowledge/claims` | Claims with evidence records |
| `GET /investigations/{id}/knowledge/relationships` | Relationships with claims/evidence |

Graph nodes include source-derived entities plus Phase 3E propositions,
evidence, hypotheses, and knowledge gaps. Edges include predicate, stance,
provenance, and supporting claim/paper identifiers. Query and limit parameters
bound graph loading.

## MeTTa and ERN-AI boundaries

MeTTa is a representation/validation target, not the canonical database. Each
generated fact includes IDs that lead back to claims, evidence, and papers. The
private PeTTa runtime parses the generated facts before the extraction job is
marked complete.

Knowledge events continue through `metta_fact_created` into the Phase 3E
reasoning event stream. ERN-AI, confidence decay, and a general-purpose NAL
rule library remain outside this phase.

## Limitations and next phase

The extractor currently handles retrieved abstracts and explicit lexical
patterns, not full-text scientific discourse, entity-linking ontologies, or
unrestricted semantic contradiction detection. Phase 3E implements bounded
structured-proposition reasoning. Future LLM or domain-specific extractors must preserve the same
source-evidence contract and pass strict schema, authorization, idempotence,
and provenance tests.
