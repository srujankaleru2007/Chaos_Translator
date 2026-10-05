from app.api.routes import _merge_results, _validate_evidence
from app.inference.schemas import ContradictionClaim, EvidenceRef, ExtractionResult, PersonClaim, TaskClaim
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
    assert checked.tasks[0].evidence[0].line_start == 2


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


@pytest.mark.parametrize("claim_data", [
    {"text": "Unowned task", "confidence": 0.6, "evidence": [{"quote": "Unowned task"}]},
    {"text": "Deadline on October 10", "confidence": 0.7, "evidence": [{"quote": "Deadline on October 10"}]},
])
def test_missing_owner_or_time_remains_optional(claim_data):
    task = TaskClaim.model_validate(claim_data)
    assert task.owner is None
    assert task.due_date is None


def test_duplicate_tasks_are_merged_without_replacing_evidence_or_confidence():
    first = ExtractionResult(summary="one", tasks=[TaskClaim(text="Send the API schema", confidence=0.8, evidence=[EvidenceRef(quote="Send the API schema")])])
    second = ExtractionResult(summary="two", tasks=[TaskClaim(text="Send the API schema.", confidence=0.7, evidence=[EvidenceRef(quote="I'll send the API schema")])])
    merged = _merge_results([first, second], 2, [], "corr")
    assert len(merged.tasks) == 1
    assert merged.tasks[0].confidence == 0.8
    assert {item.quote for item in merged.tasks[0].evidence} == {"Send the API schema", "I'll send the API schema"}


def test_contradiction_merge_preserves_both_sides_and_evidence():
    first = ExtractionResult(summary="one", contradictions=[ContradictionClaim(text="Two deadlines conflict", confidence=0.8, claim_a="10 October", claim_b="8 October", evidence=[EvidenceRef(quote="10 October")])])
    second = ExtractionResult(summary="two", contradictions=[ContradictionClaim(text="Two deadlines conflict", confidence=0.9, claim_a="10 October", claim_b="8 October", evidence=[EvidenceRef(quote="8 October")])])
    merged = _merge_results([first, second], 2, [], "corr")
    assert len(merged.contradictions) == 1
    assert merged.contradictions[0].claim_a == "10 October"
    assert merged.contradictions[0].claim_b == "8 October"
    assert {item.quote for item in merged.contradictions[0].evidence} == {"10 October", "8 October"}
    assert merged.contradictions[0].resolution is None
