"""Transparent deterministic research-plan recovery."""

from __future__ import annotations

import re
from typing import Any


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "current", "does",
    "evidence", "for", "from", "how", "in", "is", "of", "on", "or", "the",
    "this", "to", "what", "when", "which", "with",
}


def _terms(text: str) -> list[str]:
    """Extract stable, human-readable query terms without making claims."""
    terms = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", text)
    selected: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.casefold()
        if len(normalized) < 2 or normalized in _STOP_WORDS or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(term)
    return selected[:10]


def deterministic_fallback_plan(
    *, title: str, research_question: str, domain: str,
    failure_category: str = "planning_failure",
) -> dict[str, Any]:
    """Create search instructions only; never synthesize scientific findings."""
    question_terms = _terms(research_question)
    terms = question_terms or _terms(title)
    topic = " ".join(terms) or title.strip() or research_question.strip()
    phrases = [f"{left} {right}" for left, right in zip(terms, terms[1:])]
    concepts = list(dict.fromkeys([
        topic,
        *terms,
        *phrases,
        *( [f"{terms[0]} gene editing"] if terms and any(t.casefold() in {"crispr", "crispr-cas"} for t in terms) else [] ),
        *( ["CRISPR-Cas"] if any(t.casefold() == "crispr" for t in terms) else [] ),
    ]))[:10]
    domain_label = domain.strip() or "unspecified domain"
    return {
        "research_objectives": [f"Identify and characterize published research about {topic} in {domain_label}."],
        "research_questions": [research_question.strip() or title.strip()],
        "search_strategies": [
            "Search PubMed and Europe PMC using the listed concepts; normalize identifiers and deduplicate source records.",
        ],
        "key_concepts": concepts,
        "evidence_categories": ["Peer-reviewed primary research", "Reviews and clinical studies where available"],
        "reasoning_tasks": ["Extract source-linked claims, preserve polarity and uncertainty, and identify supported gaps or contradictions."],
        "phase": "planning",
        "source_note": "This is a deterministic search plan, not a scientific conclusion. No scientific literature has yet been retrieved.",
        "_metadata": {
            "orchestrator": "deterministic_fallback",
            "planning_status": "DEGRADED",
            "provider": "none",
            "model": "none",
            "trigger": failure_category,
        },
    }
