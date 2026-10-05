from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.source.models import CanonicalSource, ContentType, ContentUnit, ProcessingStatus, SourceLocator, SourceType


def unit(source_id: str, position: int = 0, **locator):
    return ContentUnit(
        source_id=source_id,
        content_type=ContentType.MESSAGE,
        text=f"unit {position}",
        position=position,
        locator=SourceLocator(source_id=source_id, **locator),
    )


def test_source_supports_all_planned_types_and_statuses():
    for source_type in SourceType:
        for status in ProcessingStatus:
            source = CanonicalSource(source_type=source_type, processing_status=status)
            assert source.source_id
            assert source.processing_status is status


def test_source_generates_stable_ids_and_preserves_multiple_ordered_units():
    source_id = "source-1"
    source = CanonicalSource(
        source_id=source_id,
        source_type=SourceType.WHATSAPP,
        units=[unit(source_id, 0, message_index=1), unit(source_id, 1, message_index=2)],
    )

    assert source.units[0].unit_id != source.units[1].unit_id
    assert [item.position for item in source.units] == [0, 1]
    assert [item.locator.message_index for item in source.units] == [1, 2]


def test_source_allows_empty_and_partial_sources_with_warnings():
    source = CanonicalSource(
        source_type=SourceType.PDF,
        processing_status=ProcessingStatus.PARTIAL,
        warnings=["Page 3 could not be decoded."],
        errors=["OCR unavailable."],
    )

    assert source.units == []
    assert source.processing_status is ProcessingStatus.PARTIAL
    assert source.warnings and source.errors


def test_locator_preserves_document_audio_and_character_provenance():
    source_id = "source-2"
    source = CanonicalSource(
        source_id=source_id,
        source_type=SourceType.AUDIO,
        units=[
            ContentUnit(
                source_id=source_id,
                content_type=ContentType.TRANSCRIPT_SEGMENT,
                text="spoken text",
                position=0,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                sender_or_speaker="Speaker 1",
                locator=SourceLocator(
                    source_id=source_id,
                    segment_index=0,
                    page_number=1,
                    timestamp_start_seconds=2.5,
                    timestamp_end_seconds=4.75,
                    character_start=10,
                    character_end=21,
                    metadata={"language": "en"},
                ),
            )
        ],
    )

    restored = CanonicalSource.model_validate_json(source.model_dump_json())
    locator = restored.units[0].locator
    assert locator.timestamp_start_seconds == 2.5
    assert locator.timestamp_end_seconds == 4.75
    assert locator.metadata["language"] == "en"
    assert restored.units[0].sender_or_speaker == "Speaker 1"


def test_invalid_unit_source_reference_is_rejected():
    with pytest.raises(ValidationError, match="locator.source_id"):
        ContentUnit(
            source_id="source-1",
            content_type=ContentType.PARAGRAPH,
            position=0,
            locator=SourceLocator(source_id="other-source", page_number=1),
        )


def test_invalid_source_units_are_rejected():
    with pytest.raises(ValidationError, match="ordered by position"):
        CanonicalSource(units=[unit("source-1", 2), unit("source-1", 1)])

    first = unit("source-1", 0)
    with pytest.raises(ValidationError, match="unique"):
        CanonicalSource(units=[first, first.model_copy()])


def test_invalid_locator_ranges_are_rejected():
    with pytest.raises(ValidationError, match="character_end"):
        SourceLocator(source_id="source-1", character_start=5, character_end=2)
