"""Faster-Whisper audio and voice-note ingestion."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from app.source.models import CanonicalSource, ContentType, ContentUnit, ExtractionMetadata, ProcessingStatus, SourceLocator, SourceType

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".webm", ".flac", ".aac"}
MIME_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac", ".aac": "audio/aac"}
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 30 * 60
AUDIO_TRANSCRIPTION_TIMEOUT_SECONDS = 300.0
AUDIO_MODEL_NAME = os.getenv("AUDIO_WHISPER_MODEL", "base")


class AudioIngestionError(RuntimeError):
    """An audio file cannot be safely or reliably ingested."""


class AudioRuntimeUnavailable(AudioIngestionError):
    """Faster-Whisper or its media decoder is unavailable."""


def _source_id(data: bytes, filename: str) -> str:
    return f"audio-{hashlib.sha256(filename.encode('utf-8') + b'\0' + data).hexdigest()[:24]}"


def validate_audio_payload(data: bytes, *, filename: str, declared_mime_type: str | None = None) -> None:
    suffix = Path(filename).suffix.casefold()
    expected_mime = MIME_TYPES.get(suffix)
    if expected_mime is None:
        raise AudioIngestionError("Only WAV, MP3, M4A, OGG, OPUS, WEBM, FLAC, and AAC audio is supported in Phase 5.")
    if len(data) > MAX_AUDIO_SIZE_BYTES:
        raise AudioIngestionError(f"Audio files must be {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
    if not data:
        raise AudioIngestionError("The audio file is empty.")
    normalized_mime = (declared_mime_type or "").split(";", 1)[0].strip().casefold()
    if normalized_mime and normalized_mime != "application/octet-stream" and normalized_mime != expected_mime:
        raise AudioIngestionError(f"The declared MIME type does not match {suffix}.")


def _probe_audio(data: bytes) -> dict[str, Any]:
    try:
        import av
    except ImportError as exc:
        raise AudioRuntimeUnavailable("The audio decoder is not installed. Install the optional audio dependencies.") from exc
    try:
        with av.open(BytesIO(data)) as container:
            streams = [stream for stream in container.streams if stream.type == "audio"]
            if not streams:
                raise AudioIngestionError("The file contains no audio stream.")
            stream = streams[0]
            duration = float(stream.duration * stream.time_base) if stream.duration is not None and stream.time_base is not None else None
            return {"duration_seconds": duration, "sample_rate": stream.sample_rate, "channels": stream.channels, "codec": stream.codec_context.name}
    except AudioIngestionError:
        raise
    except Exception as exc:
        raise AudioIngestionError("The audio container is invalid or unsupported.") from exc


def _failed_source(filename: str, data: bytes, message: str, warnings: list[str] | None = None, metadata: dict[str, Any] | None = None) -> CanonicalSource:
    all_warnings = warnings or []
    return CanonicalSource(source_id=_source_id(data, filename), source_type=SourceType.AUDIO, original_filename=filename, mime_type=MIME_TYPES.get(Path(filename).suffix.casefold()), file_size_bytes=len(data), processing_status=ProcessingStatus.FAILED, warnings=all_warnings, errors=[message], original_metadata=metadata or {}, extraction=ExtractionMetadata(method="faster_whisper", tool="faster-whisper", status=ProcessingStatus.FAILED, warnings=all_warnings, errors=[message], extracted_at=datetime.now(timezone.utc), metadata=metadata or {}))


def _remove_tempfile(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _transcribe(transcriber: Any, path: str, *, word_timestamps: bool, vad_filter: bool) -> tuple[list[Any], Any]:
    segments, info = transcriber.transcribe(path, beam_size=5, vad_filter=vad_filter, word_timestamps=word_timestamps)
    return list(segments), info


def transcribe_audio_bytes(data: bytes, *, filename: str, declared_mime_type: str | None = None, transcriber: Any | None = None, audio_probe: Callable[[bytes], dict[str, Any]] | None = None, word_timestamps: bool = True, vad_filter: bool = True, timeout_seconds: float = AUDIO_TRANSCRIPTION_TIMEOUT_SECONDS) -> CanonicalSource:
    suffix = Path(filename).suffix.casefold()
    validate_audio_payload(data, filename=filename, declared_mime_type=declared_mime_type)
    source_id = _source_id(data, filename)
    probe = audio_probe or _probe_audio
    try:
        audio_metadata = probe(data)
    except AudioRuntimeUnavailable:
        raise
    except AudioIngestionError:
        raise
    duration = audio_metadata.get("duration_seconds")
    if duration is not None and duration > MAX_AUDIO_DURATION_SECONDS:
        raise AudioIngestionError(f"Audio duration must be {MAX_AUDIO_DURATION_SECONDS // 60} minutes or less.")
    if transcriber is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AudioRuntimeUnavailable("Faster-Whisper is not installed. Install the optional audio dependencies.") from exc
        transcriber = WhisperModel(AUDIO_MODEL_NAME, device="cpu", compute_type="int8")
    temporary_path: str | None = None
    future = None
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(data)
            temporary.flush()
        future = executor.submit(_transcribe, transcriber, temporary_path, word_timestamps=word_timestamps, vad_filter=vad_filter)
        try:
            segments, info = future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            return _failed_source(filename, data, "Audio transcription exceeded its time limit.", metadata=audio_metadata)
        language = getattr(info, "language", None)
        language_probability = getattr(info, "language_probability", None)
        units: list[ContentUnit] = []
        for index, segment in enumerate(segments):
            text = str(getattr(segment, "text", "")).strip()
            if not text:
                continue
            start = float(getattr(segment, "start", 0.0))
            end = float(getattr(segment, "end", start))
            segment_metadata: dict[str, Any] = {"language": language, "language_probability": language_probability, "vad_filter": vad_filter}
            if word_timestamps and getattr(segment, "words", None) is not None:
                segment_metadata["words"] = [{"word": getattr(word, "word", ""), "start": getattr(word, "start", None), "end": getattr(word, "end", None), "probability": getattr(word, "probability", None)} for word in segment.words]
            locator = SourceLocator(source_id=source_id, segment_index=index, timestamp_start_seconds=start, timestamp_end_seconds=end, metadata=segment_metadata)
            units.append(ContentUnit(source_id=source_id, content_type=ContentType.TRANSCRIPT_SEGMENT, text=text, position=len(units), timestamp=None, locator=locator, metadata=segment_metadata))
        if not units:
            return _failed_source(filename, data, "Transcription produced no speech segments; the audio may be silent.", metadata={**audio_metadata, "language": language, "language_probability": language_probability})
        metadata = {**audio_metadata, "language": language, "language_probability": language_probability, "word_timestamps": word_timestamps, "vad_filter": vad_filter, "model": AUDIO_MODEL_NAME}
        extraction = ExtractionMetadata(method="faster_whisper", tool="faster-whisper", status=ProcessingStatus.COMPLETED, extracted_at=datetime.now(timezone.utc), metadata=metadata)
        return CanonicalSource(source_id=source_id, source_type=SourceType.AUDIO, original_filename=filename, mime_type=MIME_TYPES[suffix], file_size_bytes=len(data), processing_status=ProcessingStatus.COMPLETED, units=units, original_metadata=metadata, extraction=extraction)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        if temporary_path:
            if future is not None and not future.done():
                future.add_done_callback(lambda _completed: _remove_tempfile(temporary_path))
            else:
                _remove_tempfile(temporary_path)
