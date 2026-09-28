# Knowledge Graph 2.0

## M3 architecture audit

The M2 graph is a bounded relational projection over PostgreSQL. `Entity`
records have UUIDs, typed labels, normalized names, aliases, and source metadata.
Identity is deterministic exact normalized-name plus entity-type matching; the
extractor does not infer synonym equivalence or merge ambiguous names.
Relationships are investigation scoped, predicate typed, and stance qualified.
Claims and `RelationshipClaim` connect a relationship to the paper-backed
`Evidence` records, whose source spans preserve the exact abstract location.

Propositions are separate structured subject/predicate/object interpretations;
hypotheses, contradictions, gaps, and inference traces remain separate tables
with their own evidence/provenance links. Authenticated knowledge routes first
scope the investigation to its owner (or admin), and graph SQL filters by that
investigation. The existing `/knowledge` page provides a bounded SVG view and
entity/relationship selection, but prior entity inspection did not load the
entity's evidence neighborhood. Graph edges exposed claims without exact
evidence spans. There was no graph-specific run comparison API.

Canonical PostgreSQL records are projected into ordered MeTTa facts and
validated by private PeTTa. Snapshots already freeze entities, relationships,
propositions, evidence and reasoning records with deterministic digests; the
generic snapshot comparison already reports added, removed and changed rows.

## M3 decisions and changes

PostgreSQL remains canonical and no migration or dependency is needed. Entity
identity remains conservative: exact normalized labels within a type resolve
to the same entity; no global synonym inference or scientific alias merging is
added. Existing predicates, polarity/stance, confidence semantics, and
proposition/hypothesis separation are retained.

The entity detail API returns only entities attached to claims in the scoped
investigation. Its neighborhood includes typed relations, support claims,
paper identifiers, exact evidence text/span and polarity, plus connected
propositions and hypotheses. The graph page loads this detail on selection.
Because entity rows are globally deduplicated but aliases are not recorded
with per-investigation provenance, graph responses suppress aggregated aliases.
Snapshot entity metadata is likewise rebuilt from that investigation's claim
and paper links rather than copied from global entity metadata.
The graph diff API compares two snapshots from the same scoped investigation,
showing entities and relationships added or removed, and relationship changes
in stance, confidence, or supporting claim IDs. Snapshot manifests remain the
comparison source, so historical graph state is immutable and reproducible.

## Limits

Extraction remains conservative deterministic abstract matching and does not
provide ontology-backed entity linking. Confidence remains an extraction or
evidence signal, not a calibrated probability. Snapshot graph diff is limited
to records represented in the snapshot manifest; it does not claim semantic
equivalence between separately identified records. Run/snapshot IDs remain
available through existing reproducibility endpoints and manifests.
