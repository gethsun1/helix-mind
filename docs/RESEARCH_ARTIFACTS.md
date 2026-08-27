# HelixMind research artifacts

Phase 4B provides deterministic, private projections of an immutable
`ResearchSnapshot`. PostgreSQL remains canonical. Export generation does not
query live scientific tables, call an inference provider, or recalculate
reasoning; it reads the frozen snapshot manifest and preserves the distinction
between source evidence, system interpretation, uncertainty, and limitations.

## Supported artifacts

| Request type | Format | Content type | Contents |
| --- | --- | --- | --- |
| `MARKDOWN` | Markdown | `text/markdown` | Human-readable investigation report |
| `SCIENTIFIC_REPORT` | JSON | `application/json` | Stable machine-readable report schema |
| `OBSIDIAN_VAULT` | ZIP | `application/zip` | Obsidian-compatible linked note vault |

Artifacts are keyed by snapshot, artifact type, format, and generator version.
The worker stores a SHA-256 content digest, manifest digest, media type, byte
size, completion time, and private storage key. Generation is queued through
the existing HelixMind RQ worker and writes atomically beneath
`HELIXMIND_ARTIFACT_ROOT` (default `/opt/HelixMind/.artifacts`). The storage
directory is not served as a public web directory.

## API lifecycle

All endpoints require the authenticated bearer session and apply the same
investigation ownership rule as the rest of the API:

```text
POST /api/v1/investigations/{investigation}/snapshots/{snapshot}/artifacts
  {"artifactType":"MARKDOWN|SCIENTIFIC_REPORT|OBSIDIAN_VAULT"}
  -> 202 queued or existing artifact contract

GET /api/v1/investigations/{investigation}/snapshots/{snapshot}/artifacts
  -> lifecycle metadata and authenticated download URL when complete

GET /api/v1/investigations/{investigation}/snapshots/{snapshot}/artifacts/{artifact}/download
  -> private file content after completion
```

Repeated requests for the same queued, running, or completed contract do not
enqueue duplicate work. A failed artifact can be requested again against the
same immutable snapshot contract. Earlier snapshots and their artifacts are
never mutated by a rerun.

## Obsidian structure

The vault uses deterministic, filesystem-safe names and stable ZIP ordering:

```text
<safe-title>-<investigation-prefix>/
├── README.md
├── Research Question.md
├── Methodology.md
├── Literature/Paper-<id>.md
├── Evidence/Evidence-<id>.md
├── Propositions/Proposition-<id>.md
├── Hypotheses/Hypothesis-<id>.md
├── Knowledge Gaps/Knowledge-Gap-<id>.md
├── Reasoning/Inference-<id>.md
├── Sources/<source-record>.md
└── Manifest/{Snapshot-<id>.md, provenance.json, report.json}
```

Wikilinks connect papers, exact evidence records, propositions, hypotheses,
contradictions, gaps, and reasoning traces. References retain available DOI,
PMID, PMCID, source, and URL values. Missing identifiers remain unavailable;
HelixMind never invents citations.

## Verification boundary

Artifact confidence text describes the deterministic evidence-system assessment
already present in the snapshot. It is not a clinical probability, scientific
truth probability, or medical recommendation. Public publishing, social or
community features, leaderboards, and ERN-AI ingestion are outside Phase 4B/4C.
