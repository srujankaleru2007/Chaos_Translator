from fastapi.testclient import TestClient

from app.ingestion.whatsapp import parse_whatsapp_text
from app.main import app
from app.source.models import ContentType, ProcessingStatus, SourceType


ANDROID = """12/05/2023, 10:30 - Alice: Hello 😊 https://example.com
12/05/2023, 10:31 - Bob: This is a multiline
message with an emoji 🎉
12/05/2023, 10:32 - <Media omitted>
12/05/2023, 10:33 - Bob: This message was deleted
12/05/2023, 10:34 - Messages and calls are end-to-end encrypted.
"""

IOS = """[05/12/2023, 10:30:00 AM] Alice: iOS export
[05/12/2023, 10:31:00 AM] Bob: Follow-up
"""


def test_android_messages_map_to_ordered_canonical_units():
    source = parse_whatsapp_text(ANDROID, filename="chat.txt")

    assert source.source_type is SourceType.WHATSAPP
    assert source.original_filename == "chat.txt"
    assert source.processing_status is ProcessingStatus.PARTIAL
    assert [unit.position for unit in source.units] == list(range(5))
    assert source.units[0].content_type is ContentType.MESSAGE
    assert source.units[0].sender_or_speaker == "Alice"
    assert source.units[0].locator.message_index == 1
    assert "multiline" in source.units[1].text
    assert source.units[2].content_type is ContentType.MEDIA
    assert source.units[3].content_type is ContentType.DELETED
    assert source.units[4].content_type is ContentType.SYSTEM
    assert source.original_metadata["participants"] == ["Alice", "Bob"]


def test_ios_timestamp_and_unicode_are_preserved():
    source = parse_whatsapp_text(IOS)

    assert source.processing_status is ProcessingStatus.PARTIAL
    assert source.units[0].timestamp is not None
    assert source.units[0].text == "iOS export"
    assert any("Ambiguous date format" in warning for warning in source.warnings)


def test_malformed_lines_are_reported_without_losing_valid_messages():
    source = parse_whatsapp_text("not a message\n31/13/2023, 10:30 - Alice: valid")

    assert len(source.units) == 1
    assert source.units[0].timestamp is None
    assert source.processing_status is ProcessingStatus.PARTIAL
    assert source.errors


def test_empty_and_unrecognized_exports_are_failed():
    empty = parse_whatsapp_text("   ")
    unknown = parse_whatsapp_text("just some text")

    assert empty.processing_status is ProcessingStatus.FAILED
    assert unknown.processing_status is ProcessingStatus.FAILED
    assert unknown.errors


def test_source_ids_are_stable_for_same_input():
    assert parse_whatsapp_text(ANDROID).source_id == parse_whatsapp_text(ANDROID).source_id


def test_export_header_is_preserved_as_metadata_not_reported_as_parse_warning():
    text = "WhatsApp Chat - Project\nExported: 02/10/2026\nAll names, messages, dates, and details below are fictional.\n02/10/2026, 09:02 - Maya: Hello"
    source = parse_whatsapp_text(text)
    assert source.original_metadata["preamble"] == [
        "WhatsApp Chat - Project",
        "Exported: 02/10/2026",
        "All names, messages, dates, and details below are fictional.",
    ]
    assert source.original_metadata["participants"] == ["Maya"]
    assert not any("Unrecognized content before" in warning for warning in source.warnings)


def test_whatsapp_endpoint_returns_canonical_source():
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/whatsapp", json={"text": ANDROID, "filename": "chat.txt"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_type"] == "whatsapp"
    assert payload["units"][1]["locator"]["message_index"] == 2
    assert payload["units"][1]["text"].endswith("emoji 🎉")


def test_whatsapp_endpoint_rejects_empty_input():
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/whatsapp", json={"text": ""})

    assert response.status_code == 422
