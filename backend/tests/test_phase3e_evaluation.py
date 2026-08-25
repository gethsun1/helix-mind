"""Deterministic Phase 3E evaluation cases; no external model calls."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.scientific_reasoning import aggregate_evidence, hypothesis_status


def _evidence(*, polarity: str, paper_id=None, confidence: str = "0.990", strength: str = "0.600"):
    return SimpleNamespace(
        polarity=polarity,
        paper_id=paper_id or uuid4(),
        confidence=Decimal(confidence),
        strength=Decimal(strength),
        source_span={"start": 0, "end": 10},
        source_location="abstract",
    )


EVALUATION_CASES = [
    ("support", [_evidence(polarity="SUPPORTS")], "WEAK"),
    ("opposition", [_evidence(polarity="SUPPORTS"), _evidence(polarity="CONTRADICTS")], "CONTESTED"),
    ("insufficient", [_evidence(polarity="UNCERTAIN", confidence="0.800")], "UNRESOLVED"),
]


@pytest.mark.parametrize(("name", "items", "expected_status"), EVALUATION_CASES)
def test_phase3e_evaluation_status_cases(name, items, expected_status) -> None:
    aggregate = aggregate_evidence(items)
    assert hypothesis_status(aggregate) == expected_status, name


def test_phase3e_evaluation_competing_and_unrelated_propositions_do_not_cross_contaminate() -> None:
    target = aggregate_evidence([_evidence(polarity="SUPPORTS")])
    competing = aggregate_evidence([_evidence(polarity="CONTRADICTS")])

    assert not target.contradictory
    assert not competing.supporting
    assert hypothesis_status(target) == "WEAK"
    assert hypothesis_status(competing) == "UNRESOLVED"


def test_phase3e_evaluation_repeated_source_remains_one_independent_source() -> None:
    paper_id = uuid4()
    aggregate = aggregate_evidence([
        _evidence(polarity="SUPPORTS", paper_id=paper_id),
        _evidence(polarity="SUPPORTS", paper_id=paper_id),
    ])

    assert len(aggregate.supporting) == 2
    assert aggregate.uncertainty["supporting_sources"] == 1
    assert hypothesis_status(aggregate) == "WEAK"


def test_phase3e_evaluation_two_independent_sources_raise_confidence_deterministically() -> None:
    one_source = aggregate_evidence([_evidence(polarity="SUPPORTS", paper_id=uuid4())])
    two_sources = aggregate_evidence([
        _evidence(polarity="SUPPORTS", paper_id=uuid4()),
        _evidence(polarity="SUPPORTS", paper_id=uuid4()),
    ])

    assert two_sources.confidence > one_source.confidence
    assert aggregate_evidence(two_sources.supporting).confidence == two_sources.confidence
