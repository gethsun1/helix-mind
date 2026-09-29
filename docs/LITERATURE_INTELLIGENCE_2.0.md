# Literature Intelligence 2.0

M4 extends the canonical literature and evidence pipeline. PubMed and Europe
PMC remain the only retrieval providers. PostgreSQL `Paper`,
`InvestigationPaper`, `Evidence`, `Claim`, graph, proposition, hypothesis, and
immutable snapshot models remain canonical. No parallel literature store,
external search provider, vector index, or schema migration was added.

Investigation ownership is checked before every M4 query. A globally
canonical publication is visible in an investigation only through its
`InvestigationPaper` association; contribution paths additionally require the
investigation-scoped claim/evidence/graph links.

## API

- `GET /api/v1/investigations/{id}/literature/intelligence` returns
  investigation publications, metadata and retrieval provenance, contribution
  paths, landscape counts, identifier/title duplicate candidates, and
  limited-support coverage.
- `GET /api/v1/investigations/{id}/literature/publications/{paper_id}` returns
  a publication contribution path and auditable relevance inputs.
- `GET /api/v1/investigations/{id}/literature/publications/{paper_id}/graph`
  returns the same scoped graph contribution view for publication navigation.
- `GET /api/v1/investigations/{id}/literature/graph/{kind}/{record_id}/publications`
  resolves entity, relationship, proposition, and hypothesis support through
  persisted evidence, then returns investigation-associated publications.
- `GET /api/v1/investigations/{id}/literature/compare?leftSnapshotId=…&rightSnapshotId=…`
  compares only two snapshots owned by that investigation.

Publication contribution responses follow persisted links through
`Publication → Evidence → Claim → Entity / Relationship → Proposition →
Hypothesis`. Evidence source location, exact span, and polarity are included
when present. Missing metadata is not filled in. Relationship contributions
include the IDs of their linked evidence records.

## Identity and duplicate candidates

The preexisting persistence path resolves PMID, DOI, and PMCID, followed by a
conservative normalized title/first-author/year key. The M4 identity helper
normalizes DOI URL/prefix and PMID/PMCID prefix forms for reporting. Identifier
overlaps and exact normalized-title overlaps are reported as candidates only;
the intelligence layer never merges records. Similar or title-only matches
are not treated as canonical identity.

## Relevance formula

`literature-relevance-v1` is the weighted sum of deterministic normalized
inputs:

| Input | Weight | Normalization |
| --- | ---: | --- |
| Retrieval rank | 0.15 | `clamp(1 - (rank - 1) / 20, 0, 1)`; missing or invalid rank is 0 |
| Evidence contribution | 0.30 | `clamp(evidence_count / 3, 0, 1)` |
| Entity overlap | 0.20 | `clamp(evidence_linked_entity_count / 3, 0, 1)` |
| Proposition linkage | 0.20 | 1 when persisted evidence links to an investigation proposition, otherwise 0 |
| Hypothesis linkage | 0.15 | 1 when the linked proposition has an investigation hypothesis, otherwise 0 |

The API returns formula version, weights, normalized inputs, and score. This is
an investigation ordering/linkage signal. It never mutates evidence confidence
and does not represent scientific validity, probability, or clinical meaning.

## Landscape and coverage

The landscape distinguishes retrieved, evidence-bearing, entity-linked,
relationship-linked, proposition-linked, and hypothesis-linked publications.
It also reports provider source-record distribution, publication year, and
persisted evidence polarity. Coverage counts distinct linked publications
for investigation-scoped entities, propositions, and hypotheses. Fewer than
two links are labeled “limited retrieved evidence”; labels do not assert that
evidence is absent. The model does not invent topics for retrieved records
that have no persisted evidence or graph entity.

## Snapshot comparison

Comparison reads the immutable paper, evidence, claim, entity, relationship,
proposition, and hypothesis records inside each manifest. It reports added,
removed, and retained publications, plus per-publication contribution IDs
added, removed, or changed. Existing snapshot record digests detect changes
to a record whose ID remains stable. Historical snapshots and runs are never
rewritten or recomputed.

## Verification record

The full M4 verification report is maintained in
[`M4_LITERATURE_INTELLIGENCE_2.0_REPORT.md`](M4_LITERATURE_INTELLIGENCE_2.0_REPORT.md).
