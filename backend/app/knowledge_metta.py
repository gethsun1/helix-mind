"""Canonical knowledge to MeTTa representation and runtime validation."""

from __future__ import annotations

import re
import subprocess
import tempfile
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Claim, ClaimEntity, ClaimEvidence, Contradiction, Entity, Evidence, Hypothesis, KnowledgeGap, Proposition, Relationship, RelationshipClaim


class MettaValidationError(RuntimeError):
    pass


def _atom(value: object) -> str:
    # PeTTa's string reader does not accept backslash-escaped quotes. The
    # canonical exact text remains in PostgreSQL; MeTTa facts keep a readable
    # quote-safe projection and retain IDs back to that canonical provenance.
    text = str(value).replace("\\", "/").replace('"', "'").replace("\n", " ").strip()
    return f'"{text}"'


def render_investigation_metta(session: Session, investigation_id: object) -> str:
    """Render database facts without making the database depend on MeTTa."""
    entities = session.scalars(select(Entity).join_from(Entity, ClaimEntity, ClaimEntity.entity_id == Entity.id).join(Claim, Claim.id == ClaimEntity.claim_id).where(Claim.investigation_id == investigation_id).distinct()).all()
    claims = session.scalars(select(Claim).where(Claim.investigation_id == investigation_id)).all()
    propositions = session.scalars(select(Proposition).where(Proposition.investigation_id == investigation_id)).all()
    hypotheses = session.scalars(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id)).all()
    gaps = session.scalars(select(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation_id)).all()
    contradictions = session.scalars(select(Contradiction).where(Contradiction.investigation_id == investigation_id)).all()
    relationships = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id)).all()
    lines = ["; HelixMind provenance-preserving knowledge representation", "; generated from canonical PostgreSQL records"]
    for entity in entities:
        lines.append(f"(entity {_atom(entity.id)} {_atom(entity.canonical_name)} {_atom(entity.entity_type)})")
    for claim in claims:
        lines.append(f"(claim {_atom(claim.id)} {_atom(claim.paper_id)} {_atom(claim.claim_text)})")
        for evidence in session.scalars(select(Evidence).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id).where(ClaimEvidence.claim_id == claim.id)).all():
            lines.append(f"(evidence {_atom(evidence.id)} {_atom(evidence.paper_id)} {_atom(evidence.source_location)} {_atom(evidence.extracted_text)})")
            lines.append(f"(evidence-for {_atom(claim.id)} {_atom(evidence.id)})")
    for proposition in propositions:
        lines.append(f"(proposition {_atom(proposition.id)} {_atom(proposition.subject)} {_atom(proposition.predicate)} {_atom(proposition.object)})")
    for evidence in session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id)).all():
        if evidence.proposition_id:
            lines.append(f"(evidence-polarity {_atom(evidence.id)} {_atom(evidence.proposition_id)} {_atom(evidence.polarity or 'UNCERTAIN')})")
    for hypothesis in hypotheses:
        if hypothesis.proposition_id:
            lines.append(f"(hypothesis {_atom(hypothesis.id)} {_atom(hypothesis.proposition_id)} {_atom(hypothesis.status)} {_atom(hypothesis.confidence)})")
    for contradiction in contradictions:
        lines.append(f"(contradiction {_atom(contradiction.id)} {_atom(contradiction.proposition_id)} {_atom(contradiction.supporting_evidence_id)} {_atom(contradiction.contradictory_evidence_id)} {_atom(contradiction.contradiction_type)})")
    for gap in gaps:
        lines.append(f"(knowledge-gap {_atom(gap.id)} {_atom(gap.description)} {_atom(gap.severity)})")
    for relationship in relationships:
        lines.append(f"(relationship {_atom(relationship.id)} {_atom(relationship.subject_entity_id)} {_atom(relationship.predicate)} {_atom(relationship.object_entity_id)} {_atom(relationship.stance)})")
        for claim in session.scalars(select(Claim).join(RelationshipClaim, RelationshipClaim.claim_id == Claim.id).where(RelationshipClaim.relationship_id == relationship.id)).all():
            lines.append(f"(supported-by {_atom(relationship.id)} {_atom(claim.id)})")
    return "\n".join(lines) + "\n"


def validate_metta_text(text: str, *, runtime_root: Path | None = None) -> None:
    """Validate generated facts with PeTTa when the private runtime exists."""
    for line in text.splitlines():
        if line.startswith(";"):
            continue
        if not (line.startswith("(") and line.endswith(")") and re.match(r"\([a-z-]+(?: |\))", line)):
            raise MettaValidationError("Generated MeTTa contains unsupported syntax.")
    project_root = Path(__file__).resolve().parents[2]
    petta_root = runtime_root or project_root / ".runtime/PeTTa"
    runner = petta_root / "run.sh"
    if not runner.exists():
        raise MettaValidationError("HelixMind's private PeTTa runtime is unavailable.")
    preamble = '; HelixMind runtime validation preamble\n!(import! &self (library lib_import))\n!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git" "" "./repos" "9890bcb8041598fc6a4f1d8e658b8306a204cc87")\n'
    with tempfile.NamedTemporaryFile("w", suffix=".metta", dir=project_root / ".runtime", delete=False) as handle:
        handle.write(preamble + text)
        path = Path(handle.name)
    try:
        swi_bin = project_root / ".runtime/swi-prolog-10.1.12/bin"
        environment = os.environ.copy()
        environment["PATH"] = f"{swi_bin}:{environment.get('PATH', '')}"
        result = subprocess.run(["sh", str(runner), str(path)], cwd=petta_root, text=True, capture_output=True, timeout=60, check=False, env=environment)
        if result.returncode != 0:
            raise MettaValidationError("Generated MeTTa was rejected by the private runtime.")
    finally:
        path.unlink(missing_ok=True)
