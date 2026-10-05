# Phase 5 — Audio and voice-note ingestion

Audio ingestion is available at `POST /api/v1/sources/audio` for WAV, MP3,
M4A, OGG/OPUS, WEBM, FLAC, and AAC uploads. The endpoint bounds uploads to
50 MiB and transcription to 30 minutes of audio.

The optional `requirements-audio.txt` group provides Faster-Whisper. The
adapter uses CPU-safe `int8` inference by default, enables VAD filtering, and
requests word timestamps. It emits one canonical `transcript_segment` unit
per non-empty segment with `segment_index`, start/end seconds, detected
language metadata, and optional word-level metadata.

Timeouts, silent audio, unsupported formats, invalid containers, and missing
runtime dependencies produce explicit failed or HTTP error states. Speaker
diarization is intentionally not included in this phase.
