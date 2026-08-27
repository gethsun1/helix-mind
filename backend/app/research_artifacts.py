"""Deterministic research artifact projections.

The artifact generators consume an immutable ``ResearchSnapshot`` manifest.
They deliberately do not query live tables, call an LLM, or invent missing
scientific metadata. PostgreSQL remains authoritative; these formats are
presentation and export projections.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from app.research_reproducibility import canonical_json


GENERATOR_VERSION = "phase4b-1"
REPORT_SCHEMA_VERSION = "phase4b-report-1"
ARTIFACT_TYPES = {
    "MARKDOWN": ("RESEARCH_MARKDOWN", "markdown", "text/markdown", "md"),
    "RESEARCH_MARKDOWN": ("RESEARCH_MARKDOWN", "markdown", "text/markdown", "md"),
    "SCIENTIFIC_REPORT": ("SCIENTIFIC_REPORT", "json", "application/json", "json"),
    "OBSIDIAN": ("OBSIDIAN_VAULT", "zip", "application/zip", "zip"),
    "OBSIDIAN_VAULT": ("OBSIDIAN_VAULT", "zip", "application/zip", "zip"),
}


@dataclass(frozen=True)
class GeneratedArtifact:
    artifact_type: str
    artifact_format: str
    content_type: str
    extension: str
    content: bytes


def normalize_artifact_type(value: str) -> tuple[str, str, str, str]:
    key = value.strip().upper().replace("-", "_")
    if key not in ARTIFACT_TYPES:
        raise ValueError("Unsupported artifact type. Choose MARKDOWN, SCIENTIFIC_REPORT, or OBSIDIAN_VAULT.")
    return ARTIFACT_TYPES[key]


def _value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_value(item) for item in value]
    return value


def _manifest(snapshot: Any) -> dict[str, Any]:
    return snapshot.manifest or {}


def _id(item: dict[str, Any]) -> str:
    return str(item.get("id", ""))


def _short(value: Any, fallback: str = "Unavailable") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _safe_segment(value: str, fallback: str = "investigation") -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip().replace(" ", "-")
    value = re.sub(r"-+", "-", value).strip(".-")
    return value[:80] or fallback


def _wiki(name: str) -> str:
    return f"[[{name}]]"


def _paper_name(paper_id: Any) -> str:
    return f"Paper-{str(paper_id)}"


def _evidence_name(evidence_id: Any) -> str:
    return f"Evidence-{str(evidence_id)}"


def _proposition_name(proposition_id: Any) -> str:
    return f"Proposition-{str(proposition_id)}"


def _hypothesis_name(hypothesis_id: Any) -> str:
    return f"Hypothesis-{str(hypothesis_id)}"


def _gap_name(gap_id: Any) -> str:
    return f"Knowledge-Gap-{str(gap_id)}"


def _inference_name(inference_id: Any) -> str:
    return f"Inference-{str(inference_id)}"


def _snapshot_metadata(snapshot: Any) -> dict[str, Any]:
    manifest = _manifest(snapshot)
    investigation = manifest.get("investigation", {})
    run = manifest.get("run", {})
    return {
        "investigation_id": str(snapshot.investigation_id),
        "run_id": str(snapshot.run_id),
        "snapshot_id": str(snapshot.id),
        "snapshot_number": snapshot.snapshot_number,
        "snapshot_created_at": _value(snapshot.created_at),
        "manifest_digest": snapshot.manifest_digest,
        "schema_version": snapshot.schema_version,
        "formula_version": snapshot.formula_version,
        "metta_digest": snapshot.metta_digest,
        "run": run,
        "investigation": investigation,
    }


def _authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("full_name") or item.get("author")
            if name:
                result.append(str(name).strip())
    return result


def _paper_label(paper: dict[str, Any]) -> str:
    identifier = paper.get("doi") or paper.get("pmid") or paper.get("pmcid") or paper.get("external_id") or _id(paper)
    return f"{_short(paper.get('title'))} ({identifier})"


def _references(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    references = []
    for paper in sorted(manifest.get("papers", []), key=_id):
        references.append(
            {
                "paper_id": _id(paper),
                "title": paper.get("title"),
                "authors": _authors(paper.get("authors")),
                "journal": paper.get("journal"),
                "publication_date": paper.get("publication_date"),
                "doi": paper.get("doi"),
                "pmid": paper.get("pmid"),
                "pmcid": paper.get("pmcid"),
                "url": paper.get("url"),
                "source": paper.get("source"),
                "external_id": paper.get("external_id"),
            }
        )
    return references


def build_scientific_report(snapshot: Any) -> dict[str, Any]:
    manifest = _manifest(snapshot)
    metadata = _snapshot_metadata(snapshot)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "artifact_type": "SCIENTIFIC_REPORT",
        "generated_from": "immutable_research_snapshot",
        "investigation": metadata["investigation"],
        "methodology": {
            "research_plan": metadata["investigation"].get("research_plan", {}),
            "searches": manifest.get("searches", []),
            "provider_metadata": manifest.get("provider_metadata", []),
            "limitations": [
                "This report preserves deterministic source extraction as evidence-system interpretation, not semantic certainty.",
                "Missing source identifiers, abstracts, or relationships remain unavailable rather than being inferred.",
            ],
        },
        "reproducibility": metadata,
        "literature": manifest.get("papers", []),
        "evidence": manifest.get("evidence", []),
        "claims": manifest.get("claims", []),
        "knowledge": {
            "entities": manifest.get("entities", []),
            "relationships": manifest.get("relationships", []),
            "propositions": manifest.get("propositions", []),
        },
        "reasoning": {
            "hypotheses": manifest.get("hypotheses", []),
            "inferences": manifest.get("inferences", []),
            "contradictions": manifest.get("contradictions", []),
            "knowledge_gaps": manifest.get("knowledge_gaps", []),
            "formula_version": manifest.get("formula_version"),
            "confidence_semantics": "HelixMind evidence confidence; not scientific or clinical certainty.",
        },
        "references": _references(manifest),
        "provenance": {
            "source_manifest_digest": snapshot.manifest_digest,
            "metta_digest": snapshot.metta_digest,
            "event_count": len(manifest.get("events", [])),
            "source_of_truth": "PostgreSQL canonical records frozen in the ResearchSnapshot manifest.",
        },
    }


def build_markdown(snapshot: Any) -> str:
    report = build_scientific_report(snapshot)
    metadata = report["reproducibility"]
    investigation = report["investigation"]
    lines = [
        f"# {_short(investigation.get('title'), 'HelixMind research investigation')}",
        "",
        "> Research artifact generated from an immutable HelixMind snapshot.",
        "> Evidence, inference, hypothesis, uncertainty, and limitation remain distinct.",
        "",
        "## Research question",
        "",
        _short(investigation.get("question")),
        "",
        "## Reproducibility metadata",
        "",
        f"- Investigation ID: `{metadata['investigation_id']}`",
        f"- Run ID: `{metadata['run_id']}`",
        f"- Snapshot ID: `{metadata['snapshot_id']}`",
        f"- Snapshot number: `{metadata['snapshot_number']}`",
        f"- Snapshot manifest digest: `{metadata['manifest_digest']}`",
        f"- Schema version: `{metadata['schema_version']}`",
        f"- Formula version: `{metadata['formula_version'] or 'Unavailable'}`",
        f"- MeTTa projection digest: `{metadata['metta_digest'] or 'Unavailable'}`",
        "",
        "## Methodology",
        "",
        "The canonical research plan and source search records are preserved below. Provider metadata describes process provenance; it is not scientific evidence.",
        "",
    ]
    plan = report["methodology"].get("research_plan") or {}
    for key in ("research_objectives", "research_questions", "search_strategies", "key_concepts", "evidence_categories", "reasoning_tasks"):
        values = plan.get(key)
        if not isinstance(values, list) or not values:
            continue
        lines.extend([f"### {key.replace('_', ' ').title()}", ""])
        lines.extend(f"- {_short(item)}" for item in values)
        lines.append("")
    lines.extend(["## Literature corpus", "", f"{len(report['literature'])} canonical paper records are included.", ""])
    for paper in report["literature"]:
        lines.append(f"- {_wiki(_paper_name(_id(paper)))} — {_paper_label(paper)}; source: `{_short(paper.get('source'))}`; DOI: `{_short(paper.get('doi'), 'not recorded')}`; PMID: `{_short(paper.get('pmid'), 'not recorded')}`")
    lines.extend(["", "## Evidence", "", "Evidence below is copied from persisted source-linked records. The extraction method and source location define its limits; it is not semantic certainty.", ""])
    for evidence in sorted(report["evidence"], key=_id):
        paper_link = _wiki(_paper_name(evidence.get("paper_id"))) if evidence.get("paper_id") else "Paper unavailable"
        proposition_link = _wiki(_proposition_name(evidence.get("proposition_id"))) if evidence.get("proposition_id") else "No structured proposition"
        lines.extend([
            f"### {_evidence_name(_id(evidence))}",
            "",
            f"- Polarity: `{_short(evidence.get('polarity'), 'UNCERTAIN')}`",
            f"- Evidence type: `{_short(evidence.get('evidence_type'))}`",
            f"- Extraction method: `{_short(evidence.get('extraction_method'))}`",
            f"- Source: {paper_link}",
            f"- Proposition: {proposition_link}",
            f"- Location: `{_short(evidence.get('source_location'))}`",
            f"- Source span: `{canonical_json(evidence.get('source_span') or {})}`",
            "",
            f"> {_short(evidence.get('extracted_text'))}",
            "",
        ])
    lines.extend(["## Propositions", ""])
    for proposition in sorted(report["knowledge"]["propositions"], key=_id):
        related = [item for item in report["evidence"] if str(item.get("proposition_id")) == _id(proposition)]
        hypothesis = next((item for item in report["reasoning"]["hypotheses"] if str(item.get("proposition_id")) == _id(proposition)), None)
        links = ", ".join(_wiki(_evidence_name(_id(item))) for item in related) or "No linked evidence"
        hypothesis_link = _wiki(_hypothesis_name(_id(hypothesis))) if hypothesis else "No hypothesis"
        lines.extend([f"### {_proposition_name(_id(proposition))}", "", _short(proposition.get("description")), "", f"- Evidence: {links}", f"- Hypothesis: {hypothesis_link}", ""])
    lines.extend(["## Hypotheses", "", "Hypothesis statuses and confidence values are evidence-system assessments, not claims of scientific or clinical truth.", ""])
    for hypothesis in sorted(report["reasoning"]["hypotheses"], key=_id):
        proposition_link = _wiki(_proposition_name(hypothesis.get("proposition_id"))) if hypothesis.get("proposition_id") else "No proposition"
        lines.extend([f"### {_hypothesis_name(_id(hypothesis))}", "", f"**Statement:** {_short(hypothesis.get('statement'))}", "", f"- Status: `{_short(hypothesis.get('status'))}`", f"- Evidence confidence: `{_short(hypothesis.get('confidence'))}`", f"- Supporting evidence: `{hypothesis.get('supporting_evidence_count', 0)}`", f"- Contradictory evidence: `{hypothesis.get('contradictory_evidence_count', 0)}`", f"- Proposition: {proposition_link}", ""])
    lines.extend(["## Contradictions", ""])
    contradictions = report["reasoning"]["contradictions"]
    if not contradictions:
        lines.append("No qualifying contradictory evidence pair was recorded in this snapshot.")
        lines.append("")
    for contradiction in sorted(contradictions, key=_id):
        lines.extend([f"- `{_id(contradiction)}` — `{_short(contradiction.get('contradiction_type'))}` for {_wiki(_proposition_name(contradiction.get('proposition_id')))}; supporting evidence {_wiki(_evidence_name(contradiction.get('supporting_evidence_id')))}; contradictory evidence {_wiki(_evidence_name(contradiction.get('contradictory_evidence_id')))}"])
    lines.extend(["", "## Knowledge gaps", ""])
    gaps = report["reasoning"]["knowledge_gaps"]
    if not gaps:
        lines.append("No knowledge gaps were recorded in this snapshot.")
        lines.append("")
    for gap in sorted(gaps, key=_id):
        lines.extend([f"### {_gap_name(_id(gap))}", "", _short(gap.get("description")), "", f"- Severity: `{_short(gap.get('severity'))}`", f"- Status: `{_short(gap.get('status'))}`", f"- Evidence count: `{gap.get('evidence_count', 0)}`", f"- Contradiction count: `{gap.get('contradiction_count', 0)}`", f"- Research opportunity: {_short(gap.get('research_opportunity'), 'Not recorded')}", ""])
    lines.extend(["## Reasoning summary", "", "The following is the persisted reasoning trace and deterministic rule metadata. It is an inspectable interpretation of the evidence, not a replacement for the cited sources.", ""])
    for inference in sorted(report["reasoning"]["inferences"], key=_id):
        hypothesis_link = _wiki(_hypothesis_name(inference.get("hypothesis_id"))) if inference.get("hypothesis_id") else "No hypothesis"
        lines.extend([f"- {_wiki(_inference_name(_id(inference)))} — {hypothesis_link}; rule: `{_short(inference.get('rule_name'))}`; confidence: `{_short(inference.get('confidence'))}`; {_short(inference.get('reasoning_summary'))}"])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["methodology"]["limitations"])
    lines.extend(["", "## References", ""])
    for index, reference in enumerate(report["references"], start=1):
        identifiers = "; ".join(f"{key.upper()}: {reference[key]}" for key in ("doi", "pmid", "pmcid") if reference.get(key)) or "No DOI, PMID, or PMCID recorded"
        authors = ", ".join(reference["authors"]) or "Author information unavailable"
        lines.append(f"{index}. {_short(reference.get('title'))}. {authors}. {_short(reference.get('journal'), 'Journal unavailable')}. {identifiers}. Source: {_short(reference.get('url'), 'URL unavailable')}.")
    lines.extend(["", "---", "", f"Generated from snapshot manifest `{metadata['manifest_digest']}` with generator `{GENERATOR_VERSION}`.", ""])
    return "\n".join(lines)


def build_obsidian_files(snapshot: Any) -> dict[str, str]:
    report = build_scientific_report(snapshot)
    metadata = report["reproducibility"]
    investigation = report["investigation"]
    root = f"{_safe_segment(_short(investigation.get('title'), 'investigation'))}-{metadata['investigation_id'][:8]}"
    files: dict[str, str] = {}

    def add(relative: str, content: str) -> None:
        files[f"{root}/{relative}"] = content.rstrip() + "\n"

    snapshot_link = _wiki(f"Manifest/Snapshot-{metadata['snapshot_id']}")
    add("README.md", "\n".join([
        f"# {_short(investigation.get('title'), 'HelixMind investigation')}",
        "",
        "This vault is an export projection of a canonical HelixMind research snapshot.",
        "",
        f"- Research question: {_short(investigation.get('question'))}",
        f"- Snapshot: {snapshot_link}",
        f"- Methodology: {_wiki('Methodology')}",
        f"- Literature: {len(report['literature'])} papers",
        f"- Evidence: {len(report['evidence'])} records",
        f"- Hypotheses: {len(report['reasoning']['hypotheses'])}",
        f"- Knowledge gaps: {len(report['reasoning']['knowledge_gaps'])}",
        "",
        "## Index",
        "",
        "- Literature",
        "- Evidence",
        "- Propositions",
        "- Hypotheses",
        "- Knowledge Gaps",
        "- Reasoning",
        "- Sources",
        "- Manifest",
    ]))
    add("Research Question.md", f"# Research Question\n\n{_short(investigation.get('question'))}\n\n- Investigation ID: `{metadata['investigation_id']}`\n- Domain: `{_short(investigation.get('domain'))}`\n- Snapshot: `{metadata['snapshot_id']}`\n")
    plan_lines = ["# Methodology", "", "The methodology is the persisted research plan and source search record.", ""]
    plan = report["methodology"].get("research_plan") or {}
    for key, values in plan.items():
        if isinstance(values, list):
            plan_lines.extend([f"## {key.replace('_', ' ').title()}", ""])
            plan_lines.extend(f"- {_short(item)}" for item in values)
            plan_lines.append("")
    plan_lines.extend(["## Search records", ""])
    plan_lines.extend(f"- `{_short(item.get('source'))}` — `{_short(item.get('status'))}` — `{_short(item.get('query'))}`" for item in report["methodology"]["searches"])
    add("Methodology.md", "\n".join(plan_lines))

    for paper in report["literature"]:
        name = _paper_name(_id(paper))
        evidence_links = [_wiki(_evidence_name(_id(item))) for item in report["evidence"] if str(item.get("paper_id")) == _id(paper)]
        add(f"Literature/{name}.md", "\n".join([
            f"# {_short(paper.get('title'))}", "", f"- Source: `{_short(paper.get('source'))}`", f"- External ID: `{_short(paper.get('external_id'))}`", f"- DOI: `{_short(paper.get('doi'), 'Not recorded')}`", f"- PMID: `{_short(paper.get('pmid'), 'Not recorded')}`", f"- PMCID: `{_short(paper.get('pmcid'), 'Not recorded')}`", f"- Retrieved at: `{_short(paper.get('retrieved_at'))}`", "", "## Abstract", "", _short(paper.get("abstract"), "Abstract unavailable from source."), "", "## Evidence links", "", ", ".join(evidence_links) or "No evidence records linked.",
        ]))
        add(f"Sources/{name}.md", f"# Source record — {_short(paper.get('title'))}\n\n- Provider: `{_short(paper.get('source'))}`\n- URL: {_short(paper.get('url'), 'Unavailable')}\n- Retrieved at: `{_short(paper.get('retrieved_at'))}`\n- External ID: `{_short(paper.get('external_id'))}`\n")

    for evidence in report["evidence"]:
        links = []
        if evidence.get("paper_id"):
            links.append(_wiki(_paper_name(evidence["paper_id"])))
        if evidence.get("proposition_id"):
            links.append(_wiki(_proposition_name(evidence["proposition_id"])))
        add(f"Evidence/{_evidence_name(_id(evidence))}.md", "\n".join([
            f"# {_evidence_name(_id(evidence))}", "", f"> {_short(evidence.get('extracted_text'))}", "", f"- Polarity: `{_short(evidence.get('polarity'), 'UNCERTAIN')}`", f"- Extraction method: `{_short(evidence.get('extraction_method'))}`", f"- Source location: `{_short(evidence.get('source_location'))}`", f"- Source span: `{canonical_json(evidence.get('source_span') or {})}`", f"- Related records: {', '.join(links) or 'Unavailable'}",
        ]))

    for proposition in report["knowledge"]["propositions"]:
        evidence_links = [_wiki(_evidence_name(_id(item))) for item in report["evidence"] if str(item.get("proposition_id")) == _id(proposition)]
        hypotheses = [item for item in report["reasoning"]["hypotheses"] if str(item.get("proposition_id")) == _id(proposition)]
        hypothesis_links = [_wiki(_hypothesis_name(_id(item))) for item in hypotheses]
        add(f"Propositions/{_proposition_name(_id(proposition))}.md", "\n".join([
            f"# {_proposition_name(_id(proposition))}", "", _short(proposition.get("description")), "", f"- Subject: `{_short(proposition.get('subject'))}`", f"- Predicate: `{_short(proposition.get('predicate'))}`", f"- Object: `{_short(proposition.get('object'))}`", f"- Evidence: {', '.join(evidence_links) or 'None linked'}", f"- Hypotheses: {', '.join(hypothesis_links) or 'None linked'}",
        ]))

    for hypothesis in report["reasoning"]["hypotheses"]:
        proposition_link = _wiki(_proposition_name(hypothesis.get("proposition_id"))) if hypothesis.get("proposition_id") else "No proposition"
        support_links = [_wiki(_evidence_name(_id(item))) for item in report["evidence"] if str(item.get("proposition_id")) == str(hypothesis.get("proposition_id")) and item.get("polarity") == "SUPPORTS"]
        opposing_links = [_wiki(_evidence_name(_id(item))) for item in report["evidence"] if str(item.get("proposition_id")) == str(hypothesis.get("proposition_id")) and item.get("polarity") == "CONTRADICTS"]
        gaps = [_wiki(_gap_name(_id(item))) for item in report["reasoning"]["knowledge_gaps"] if str(item.get("hypothesis_id")) == _id(hypothesis)]
        add(f"Hypotheses/{_hypothesis_name(_id(hypothesis))}.md", "\n".join([
            f"# {_hypothesis_name(_id(hypothesis))}", "", f"**Statement:** {_short(hypothesis.get('statement'))}", "", f"- Status: `{_short(hypothesis.get('status'))}`", f"- Evidence confidence: `{_short(hypothesis.get('confidence'))}`", f"- Proposition: {proposition_link}", f"- Supporting evidence: {', '.join(support_links) or 'None recorded'}", f"- Contradictory evidence: {', '.join(opposing_links) or 'None recorded'}", f"- Knowledge gaps: {', '.join(gaps) or 'None recorded'}",
        ]))

    for gap in report["reasoning"]["knowledge_gaps"]:
        related = []
        if gap.get("hypothesis_id"):
            related.append(_wiki(_hypothesis_name(gap["hypothesis_id"])))
        if gap.get("proposition_id"):
            related.append(_wiki(_proposition_name(gap["proposition_id"])))
        add(f"Knowledge Gaps/{_gap_name(_id(gap))}.md", f"# {_gap_name(_id(gap))}\n\n{_short(gap.get('description'))}\n\n- Severity: `{_short(gap.get('severity'))}`\n- Status: `{_short(gap.get('status'))}`\n- Evidence count: `{gap.get('evidence_count', 0)}`\n- Related records: {', '.join(related) or 'Unavailable'}\n- Research opportunity: {_short(gap.get('research_opportunity'), 'Not recorded')}\n")

    for inference in report["reasoning"]["inferences"]:
        hypothesis_link = _wiki(_hypothesis_name(inference.get("hypothesis_id"))) if inference.get("hypothesis_id") else "No hypothesis"
        add(f"Reasoning/{_inference_name(_id(inference))}.md", f"# {_inference_name(_id(inference))}\n\n- Rule: `{_short(inference.get('rule_name'))}`\n- Confidence: `{_short(inference.get('confidence'))}`\n- Hypothesis: {hypothesis_link}\n\n{_short(inference.get('reasoning_summary'))}\n\n```json\n{canonical_json(inference.get('metadata') or {})}\n```\n")

    add(f"Manifest/Snapshot-{metadata['snapshot_id']}.md", f"# Snapshot manifest\n\n```json\n{canonical_json(report['reproducibility'])}\n```\n\nSource manifest digest: `{metadata['manifest_digest']}`\n")
    add("Manifest/provenance.json", canonical_json(report["provenance"]))
    add("Manifest/report.json", canonical_json(report))
    return dict(sorted(files.items()))


def build_obsidian_zip(snapshot: Any) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in build_obsidian_files(snapshot).items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def generate_artifact(snapshot: Any, requested_type: str) -> GeneratedArtifact:
    artifact_type, artifact_format, content_type, extension = normalize_artifact_type(requested_type)
    if artifact_type == "RESEARCH_MARKDOWN":
        content = build_markdown(snapshot).encode("utf-8")
    elif artifact_type == "SCIENTIFIC_REPORT":
        content = (canonical_json(build_scientific_report(snapshot)) + "\n").encode("utf-8")
    else:
        content = build_obsidian_zip(snapshot)
    return GeneratedArtifact(artifact_type, artifact_format, content_type, extension, content)
