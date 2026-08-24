# Literature pipeline

HelixMind retrieves scientific literature from official public APIs only:

| Source | Retrieval path | Stored identity |
| --- | --- | --- |
| PubMed / NCBI | ESearch, then EFetch XML | PMID, DOI where supplied |
| Europe PMC | REST `search` with `resultType=core` | Europe PMC source/id, or canonical PMID where present |

`app.literature.LiteratureClient` exposes a provider registry implementing the
`LiteratureProvider` contract. The current `PubMed` and `Europe PMC` adapters
normalize title, abstract, authors, publication date, DOI/PMID/PMCID, URLs,
publication metadata, source metadata, and the exact search query. They do not
invent records. `investigation_papers` plus `research_searches` preserve the
many-to-many provenance between an investigation and each persisted paper.

Canonical papers are deduplicated in PMID, DOI, PMCID, provider-ID order, with
a conservative title/author/year fallback. A paper may retain multiple source
records while remaining one canonical database row. Paper detail exposes the
investigation, query, provider ID, retrieval timestamp, source URL, and search
status for each provenance entry.

For the flagship question, the deterministic pre-planning query is:

```text
PubMed:     ("sickle cell disease"[Title/Abstract]) AND (CRISPR[Title/Abstract] OR "gene editing"[Title/Abstract])
Europe PMC: (TITLE_ABS:"sickle cell disease") AND (TITLE_ABS:CRISPR OR TITLE_ABS:"gene editing")
```

This conservative query builder exists to avoid treating a natural-language
question as valid database syntax. The worker records the OmegaClaw-generated
structured research plan before running this stage; richer multi-query
expansion remains future work.

## Verified local run

On 2026-08-21, a local `POST /api/v1/investigations` for the flagship question
completed through the RQ worker. The worker retrieved and
persisted 18 distinct papers with no PubMed or Europe PMC source failures.
The investigation event stream recorded `literature_search_started`,
`papers_found`, one `paper_ingested` event per persisted paper, and
`literature_search_completed`.

The stage retrieves and persists evidence sources only. It emits structured
investigation events for search start/completion/failure, normalization,
deduplication, persistence, and final completion. It does not yet infer claims,
score evidence, or treat paper titles/abstracts as clinical truth. MeTTa and
ERN-AI consume a future normalized event boundary; neither is implemented here.
