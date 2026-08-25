"""Conservative, source-grounded knowledge extraction primitives.

This module deliberately does not ask an LLM to invent scientific facts. It
extracts exact abstract sentences as claims and only emits relationships when
the source sentence contains an explicit supported predicate.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


PREDICATES = ("TARGETS", "INHIBITS", "ACTIVATES", "REGULATES", "ENCODES", "EXPRESSED_IN", "ASSOCIATED_WITH", "CORRELATES_WITH", "INVESTIGATED_FOR", "IMPROVES", "RESTORES", "REDUCES", "INCREASES", "CORRECTS")
_PREDICATE_PATTERNS = {
    "TARGETS": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:targets|targeting|targeted|target)\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "INHIBITS": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:inhibits|inhibited|inhibit)\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "ACTIVATES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:activates|activated|activate)\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "REGULATES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:regulates|regulated|regulate)\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "ENCODES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?encodes?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "EXPRESSED_IN": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:is\s+)?expressed\s+in\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "ASSOCIATED_WITH": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:is\s+)?associated\s+with\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "CORRELATES_WITH": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?correlates?\s+with\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "INVESTIGATED_FOR": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?(?:was\s+)?investigated\s+for\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "IMPROVES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?improves?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "RESTORES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?restores?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "REDUCES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?reduces?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "INCREASES": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?increases?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
    "CORRECTS": r"\b(?P<subject>[A-Za-z][A-Za-z0-9-]{1,80})\s+(?:does not |did not |do not |failed to )?corrects?\s+(?P<object>[A-Za-z][A-Za-z0-9-]{1,80})\b",
}


@dataclass(frozen=True)
class EntityCandidate:
    name: str
    entity_type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceCandidate:
    text: str
    start: int
    end: int
    source_location: str = "abstract"
    section: str | None = None


@dataclass(frozen=True)
class ClaimCandidate:
    text: str
    evidence: EvidenceCandidate
    extraction_confidence: float = 0.99


@dataclass(frozen=True)
class RelationshipCandidate:
    subject: str
    predicate: str
    object: str
    claim_text: str


@dataclass
class ExtractionResult:
    entities: list[EntityCandidate] = field(default_factory=list)
    claims: list[ClaimCandidate] = field(default_factory=list)
    relationships: list[RelationshipCandidate] = field(default_factory=list)


class KnowledgeExtractor(Protocol):
    name: str

    def extract(self, *, title: str, abstract: str | None, keywords: list[str], mesh_terms: list[str]) -> ExtractionResult:
        ...


def normalize_entity_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def normalize_claim(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def claim_hash(investigation_id: object, paper_id: object, text: str) -> str:
    return hashlib.sha256(f"{investigation_id}:{paper_id}:{normalize_claim(text)}".encode()).hexdigest()


def _entity_type(value: str) -> str:
    normalized = normalize_entity_name(value)
    if re.fullmatch(r"[A-Z]{2,8}", value):
        return "GENE"
    if any(token in normalized for token in ("disease", "syndrome", "cancer", "infection")):
        return "DISEASE"
    if any(token in normalized for token in ("protein", "receptor", "kinase")):
        return "PROTEIN"
    if any(token in normalized for token in ("cell", "neuron", "lymphocyte")):
        return "CELL_TYPE"
    if any(token in normalized for token in ("crispr", "cas9", "gene editing", "sequencing")):
        return "TECHNOLOGY"
    if any(token in normalized for token in ("therapy", "treatment", "intervention", "drug")):
        return "INTERVENTION"
    return "OTHER"


class DeterministicKnowledgeExtractor:
    """High-precision extractor using only source-provided text and terms."""

    name = "deterministic_abstract"

    def extract(self, *, title: str, abstract: str | None, keywords: list[str], mesh_terms: list[str]) -> ExtractionResult:
        source_text = " ".join(part for part in (title, abstract or "") if part).strip()
        result = ExtractionResult()
        names: dict[str, EntityCandidate] = {}
        for value in [*keywords, *mesh_terms]:
            cleaned = str(value).strip()
            if cleaned and normalize_entity_name(cleaned):
                key = normalize_entity_name(cleaned)
                names.setdefault(key, EntityCandidate(cleaned, _entity_type(cleaned)))
        for value in re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", source_text):
            key = normalize_entity_name(value)
            names.setdefault(key, EntityCandidate(value, _entity_type(value)))
        for candidate in names.values():
            if re.search(rf"(?<![A-Za-z]){re.escape(candidate.name)}(?![A-Za-z])", source_text, re.IGNORECASE):
                result.entities.append(candidate)

        if not abstract:
            return result
        for match in re.finditer(r"[^.!?]+(?:[.!?]|$)", abstract):
            sentence = match.group(0).strip()
            if len(sentence.split()) < 3:
                continue
            start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            end = start + len(sentence)
            evidence = EvidenceCandidate(sentence, start, end)
            result.claims.append(ClaimCandidate(sentence, evidence))
            for predicate, pattern in _PREDICATE_PATTERNS.items():
                relation = re.search(pattern, sentence, re.IGNORECASE)
                if relation:
                    subject = relation.group("subject")
                    object_name = relation.group("object")
                    result.entities.extend([
                        EntityCandidate(subject, _entity_type(subject)),
                        EntityCandidate(object_name, _entity_type(object_name)),
                    ])
                    result.relationships.append(RelationshipCandidate(subject, predicate, object_name, sentence))
        unique_entities = {(normalize_entity_name(item.name), item.entity_type): item for item in result.entities}
        result.entities = list(unique_entities.values())
        unique_relationships = {(normalize_entity_name(item.subject), item.predicate, normalize_entity_name(item.object), normalize_claim(item.claim_text)): item for item in result.relationships}
        result.relationships = list(unique_relationships.values())
        return result
