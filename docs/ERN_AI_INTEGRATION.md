# ERN-AI integration boundary

Status: proposal only. ERN-AI is not implemented, configured, or required by
the current HelixMind runtime.

## Purpose and proposed flow

An event-driven layer could assess whether a literature or research event is
significant, how frequently or strongly it occurs, and whether it should update
an investigation state:

```text
Research event → event normalization → ERN-AI significance assessment
               → frequency / strength → confidence → MeTTa representation
               → NAL / PLN reasoning → research-state update
```

The adapter must be replaceable. Core persistence and provenance must not
depend on one model, vendor, or event-reasoning implementation.

## Proposed interface and schema

An implementation could expose a local Python protocol or process boundary:

```python
class EventSignificanceAdapter(Protocol):
    def assess(self, event: ResearchEvent) -> EventAssessment: ...
```

The interface should be versioned and explicit about failure. An unavailable
adapter produces `assessment_unavailable`, never an invented confidence value.

```json
{
  "event_id": "uuid",
  "schema_version": "1.0",
  "event_type": "paper_retrieved",
  "occurred_at": "2026-08-24T00:00:00Z",
  "investigation_id": "uuid",
  "subject": {"kind": "paper", "id": "uuid"},
  "payload": {},
  "provenance": {"source": "PUBMED", "source_record_id": "pmid", "source_query": "exact query"}
}
```

Possible outputs include `significance`, `frequency`, `strength`, `confidence`,
signals, adapter/version metadata, and supporting source provenance. Each scale
must be documented and calibrated. These are research signals, not clinical
probabilities, effect sizes, or causal certainty.

## Relationship to HelixMind reasoning

- OmegaClaw could orchestrate an assessment request under a restricted policy.
- MeTTa could represent the normalized event and source links as explicit facts.
- NAL/PLN could derive inspectable relationships from those facts.
- PostgreSQL investigation events should retain the original event, adapter
  result, versions, and failure state.

ERN-AI must not bypass server-side authorization, source provenance, or the
existing queue boundary.

## Implementation phases

1. Define and test versioned event and assessment schemas with fixtures.
2. Add a deterministic reference adapter with explicit uncertainty.
3. Persist assessments and provenance without changing scientific conclusions.
4. Add MeTTa serialization and inspectable NAL/PLN rules.
5. Evaluate adapters against replayable, source-grounded datasets.
6. Expose research-state signals only after validation.

## Security and testing

Inputs are untrusted. Validate schema versions, enforce investigation ownership,
reject client-supplied roles, constrain process capabilities, and keep provider
credentials server-side. Never grant an adapter shell, filesystem, network, or
cross-tenant access by default.

Tests should cover schema validation, replay determinism, provenance retention,
contradictory inputs, timeouts, authorization, failure classification, and the
distinction between confidence, truth values, and clinical probability.
