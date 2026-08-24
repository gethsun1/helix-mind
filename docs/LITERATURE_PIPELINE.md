# Literature pipeline

HelixMind retrieves scientific literature from official public APIs only:

| Source | Retrieval path | Stored identity |
| --- | --- | --- |
| PubMed / NCBI | ESearch, then EFetch XML | PMID, DOI where supplied |
| Europe PMC | REST `search` with `resultType=core` | Europe PMC source/id, or canonical PMID where present |

`app.literature.LiteratureClient` normalizes title, abstract, authors,
publication date, DOI, URL, source metadata, and the exact search query. It
does not invent records. `investigation_papers` preserves the many-to-many
provenance between an investigation and each persisted paper.

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
reached `literature_ready` through the RQ worker. The worker retrieved and
persisted 18 distinct papers with no PubMed or Europe PMC source failures.
The investigation event stream recorded `literature_search_started`,
`papers_found`, one `paper_ingested` event per persisted paper, and
`literature_search_completed`.

The stage retrieves and persists evidence sources only. It does not yet infer
claims, score evidence, or treat paper titles/abstracts as clinical truth.
