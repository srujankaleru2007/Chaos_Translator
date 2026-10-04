from app.api.routes import _validate_evidence
from app.inference.schemas import EvidenceRef, ExtractionResult, PersonClaim, TaskClaim
from app.inference.provider import ProviderError
import pytest


def test_structured_categories_preserve_exact_evidence():
    result = ExtractionResult(
        summary="Project discussion",
        people=[PersonClaim(
            name="Asha", text="Asha owns the API work", confidence=0.9,
            evidence=[EvidenceRef(quote="Asha owns the API work", line_start=1)],
        )],
        tasks=[TaskClaim(
            text="Fix the endpoint", confidence=0.8,
            evidence=[EvidenceRef(quote="Fix the endpoint", message_index=2)],
        )],
    )
    checked = _validate_evidence(result, "Asha owns the API work\nFix the endpoint")
    assert checked.people[0].evidence[0].line_start == 1
    assert checked.tasks[0].evidence[0].message_index == 2


def test_unsupported_evidence_is_rejected():
    result = ExtractionResult(
        summary="",
        people=[PersonClaim(
            name="Asha", text="Asha owns it", confidence=0.9,
            evidence=[EvidenceRef(quote="Asha owns the database")],
        )],
    )
    with pytest.raises(ProviderError, match="unsupported evidence"):
        _validate_evidence(result, "Asha owns the API")


def test_empty_categories_are_valid():
    result = ExtractionResult(summary="No actionable intelligence")
    assert result.people == []
    assert result.contradictions == []
