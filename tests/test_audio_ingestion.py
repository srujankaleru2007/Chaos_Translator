from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ingestion.audio import AudioIngestionError, AudioRuntimeUnavailable, transcribe_audio_bytes
from app.main import app
from app.source.models import ContentType, ProcessingStatus


def probe(data: bytes):
    return {"duration_seconds": 4.5, "sample_rate": 16_000, "channels": 1, "codec": "wav"}


class FakeTranscriber:
    def transcribe(self, path, **kwargs):
        word = SimpleNamespace(word=" hello", start=0.0, end=0.4, probability=0.99)
        segment = SimpleNamespace(start=0.0, end=1.2, text=" Hello world ", words=[word])
        return iter([segment]), SimpleNamespace(language="en", language_probability=0.98)


def test_transcription_preserves_segment_and_word_provenance():
    source = transcribe_audio_bytes(b"audio bytes", filename="voice.wav", transcriber=FakeTranscriber(), audio_probe=probe)

    assert source.processing_status == ProcessingStatus.COMPLETED
    assert source.units[0].content_type == ContentType.TRANSCRIPT_SEGMENT
    assert source.units[0].text == "Hello world"
    assert source.units[0].locator.segment_index == 0
    assert source.units[0].locator.timestamp_start_seconds == 0.0
    assert source.units[0].locator.timestamp_end_seconds == 1.2
    assert source.units[0].metadata["words"][0]["word"] == " hello"
    assert source.original_metadata["language"] == "en"


def test_silent_audio_is_failed_without_fabricated_text():
    class SilentTranscriber:
        def transcribe(self, path, **kwargs):
            return iter([]), SimpleNamespace(language="en", language_probability=0.1)

    source = transcribe_audio_bytes(b"audio bytes", filename="silent.wav", transcriber=SilentTranscriber(), audio_probe=probe)

    assert source.processing_status == ProcessingStatus.FAILED
    assert "silent" in source.errors[0]
    assert source.units == []


def test_duration_limit_is_enforced():
    with pytest.raises(AudioIngestionError, match="30 minutes"):
        transcribe_audio_bytes(b"audio bytes", filename="long.wav", transcriber=FakeTranscriber(), audio_probe=lambda data: {"duration_seconds": 1801})


def test_timeout_returns_failed_source():
    class SlowTranscriber:
        def transcribe(self, path, **kwargs):
            import time
            time.sleep(0.05)
            return iter([]), SimpleNamespace()

    source = transcribe_audio_bytes(b"audio bytes", filename="slow.wav", transcriber=SlowTranscriber(), audio_probe=probe, timeout_seconds=0.001)

    assert source.processing_status == ProcessingStatus.FAILED
    assert "time limit" in source.errors[0]


def test_missing_audio_runtime_is_explicit():
    with pytest.raises(AudioRuntimeUnavailable, match="audio decoder"):
        transcribe_audio_bytes(b"audio bytes", filename="voice.wav", transcriber=FakeTranscriber())


def test_unsupported_audio_extension_is_rejected():
    with pytest.raises(AudioIngestionError, match="Only WAV"):
        transcribe_audio_bytes(b"audio bytes", filename="voice.txt", transcriber=FakeTranscriber(), audio_probe=probe)


def test_audio_endpoint_rejects_unsupported_extension():
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/audio", files={"file": ("voice.txt", b"audio bytes", "text/plain")})

    assert response.status_code == 422
