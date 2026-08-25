# Phase 3E scientific reasoning

Phase 3E extends the Phase 3D provenance graph into a deterministic,
inspectable reasoning layer:

```text
Question → OmegaClaw plan → PubMed / Europe PMC
         → paper → exact abstract evidence → structured proposition
         → hypothesis → explicit evidence balance → trace / gaps
```

Literature remains the evidence source of truth. The LLM provider may plan or
interpret language, but the Phase 3E aggregation path uses persisted
paper-linked evidence and does not ask an LLM for a confidence number.

## Evidence and propositions

An `Evidence` record points to a canonical paper, exact abstract span,
extraction method, proposition, polarity, strength signal, and extraction
confidence. The supported polarities are `SUPPORTS`, `CONTRADICTS`, `NEUTRAL`,
and `UNCERTAIN`. A sentence without an opposing or uncertainty cue is treated
as supporting only within this extraction model; that is not a scientific
truth claim.

An explicit subject/predicate/object `Proposition` has a stable hash within an
investigation. Multiple source evidence records can reference the same
proposition. Propositions are created only when the deterministic extractor
finds an explicit relationship in source text.

## Hypotheses and confidence

Each proposition receives a qualified hypothesis. Statuses are evidence-state
labels: `SUPPORTED`, `CONTESTED`, `WEAK`, or `UNRESOLVED`. They do not mean
scientifically true or false.

The current HelixMind evidence confidence formula is:

```text
0.45 × polarity_balance × extraction_quality ×
      (0.5 + 0.5 × independent_support_sources / 3)
+ 0.25 × independent_support_sources / 3
+ 0.20 × mean_extraction_confidence
+ 0.10 × provenance_completeness
```

`extraction_quality` is the mean of the stored abstract extraction strength
and extraction confidence. For the deterministic abstract extractor, strength
is an explicit `0.600` assessment signal for an exact abstract sentence; it is
not a study-quality or clinical-efficacy score. The result is labelled
**HelixMind evidence confidence**, not probability that a hypothesis is true.

## Contradictions and gaps

Contradictions are created only for opposing evidence attached to the same
structured proposition. Each record retains both evidence IDs, papers,
source spans, a contradiction type (`DIRECT`, `CONTEXTUAL`, or
`INSUFFICIENT_EVIDENCE`), and provenance. Different conclusions without a
shared proposition are not automatically called contradictory.

A knowledge gap is emitted for absent support, low evidence confidence, or a
contested evidence balance. It includes a rationale, severity, source counts,
provenance, and a clearly labelled **Potential research opportunity**. These
are research suggestions, not medical recommendations.

## MeTTa / PLN boundary

The canonical database remains authoritative. Phase 3E renders propositions,
polarity, hypotheses, contradictions, and gaps into the existing MeTTa
representation and validates that representation through the private PeTTa
runtime. The persisted reasoning trace records the proposition, evidence IDs,
relationships, rule, result, confidence, and uncertainty.

The implemented deterministic rule is `direct_evidence_balance`. The reusable
`transitive_support` primitive expresses the bounded PLN-style rule that two
support edges can derive a third support edge; it does not authorize arbitrary
LLM reasoning. A larger NAL rule library remains future work.

## Lifecycle, API, and safety

Investigations now expose `KNOWLEDGE` and `REASONING` worker stages between
literature retrieval and completion. Events include reasoning start/completion,
proposition and hypothesis creation, contradiction detection, and knowledge
gap detection. No literature is fabricated when a provider returns no records.

Owner-scoped endpoints are available at:

- `GET /api/v1/investigations/{id}/evidence`
- `GET /api/v1/investigations/{id}/hypotheses`
- `GET /api/v1/investigations/{id}/contradictions`
- `GET /api/v1/investigations/{id}/knowledge-gaps`
- `GET /api/v1/investigations/{id}/reasoning`
- `GET /api/v1/investigations/{id}/reasoning/trace`

The investigation workspace shows source-linked evidence, evidence balance,
opposing evidence, gaps, opportunities, and the reasoning trace. If no
contradiction was found in the retrieved corpus, the UI says so explicitly.

ERN-AI and Obsidian export are not implemented in this phase. The proposition,
evidence, hypothesis, gap, provenance, and trace structures are intentionally
clean boundaries for those future integrations.
