# Implementation log

2026-10-03: inspected the existing single-model Ollama provider, extraction schema, route, tests, and repository documentation. Added centralized primary/fallback settings, bounded retry and fallback selection, strict shared-schema validation, configurable output-token limits, and model diagnostics in the health response. No model downloads were performed.

Verification: `python -m pytest -q` could not start because pytest is not installed. `python -m unittest discover -v` and the provider test also could not import because project dependencies (including pandas and pydantic) are not installed in this environment.

2026-10-04 remediation: unified the frontend inference client, added client/server input validation, categorized provider failures, sanitized 503 responses, added fallback/error contract tests, aligned E4B/E2B defaults, removed the remote Google Font build dependency, and installed pytest/httpx2. Contract tests: 5 passed. Full frontend lint remains blocked by legacy components; production build compiles but the TypeScript worker returns Windows spawn EPERM.

2026-10-03 debug: `POST /api/v1/inference/test` with `{}` returned HTTP 422 with Pydantic detail `body.text: Field required`; the normal `{text, source_type}` payload passes request validation. Backend health and Ollama `/api/tags` respond, but direct Ollama generation and valid inference requests did not complete within the test window, causing provider-side failure/503. Added primary/fallback availability fields to health diagnostics and exposed HTTP status in frontend errors. No models were downloaded.

2026-10-04 structured intelligence Phases 3–6: expanded typed schemas for people, tasks, deadlines, decisions, questions, technical issues, dependencies, and contradictions; added deterministic quote-to-line/message/timestamp locator generation; rejected unsupported model evidence; updated frontend API types and rendering with category sections, empty states, expandable evidence, uncertainty labels, and contradiction details; added regression coverage. Verification: focused backend suite passed after correction; full synthetic chat still requires chunking because the current request can exceed the inference runtime budget.

2026-10-04 frontend runtime TypeError: traced the crash to `claims.length`/`claims.map` in the active category loop after `extractIntelligence()` cast unvalidated JSON to `ExtractionResult`. Added strict runtime response parsing with optional-array normalization and required-field/evidence validation. No fallback intelligence is fabricated.

2026-10-04 inference 503 investigation: `/api/tags` showed both models available. A short input succeeded with all typed categories in 68.9 seconds. The full 6,187-byte synthetic chat timed out on E4B and produced truncated output on E2B, causing the 503 after all retries. Changed retry policy to avoid repeating deterministic timeout/output failures, added correlation IDs and safe failure categories to 503 responses, retained fallback activation, and preserved detailed server logs.

2026-10-04 Groq fallback: added a backend-only OpenAI-compatible Groq adapter, configurable model/key, shared 45-second local budget, explicit request consent, provider metadata, categorized cloud failures, mocked fallback tests, and frontend consent control. No live Groq key was used.

2026-10-04 cloud UX and long-input support: replaced the per-request API-only consent path with a persistent frontend preference, raised the request ceiling to 200,000 characters, added WhatsApp boundary chunking and aggregation, preserved evidence against the original source, and exposed partial/failed-chunk metadata.

2026-10-04 Groq live fix: independent tests proved the key and model were valid. The project Python adapter received HTTP 403 until an explicit User-Agent was added. `openai/gpt-oss-20b` then passed the adapter and live fallback tests; no credential was persisted.

2026-10-04 Phase 3 document ingestion: added the Docling-backed PDF/DOCX/PPTX adapter, canonical source provenance mapping, temporary-file conversion boundary, explicit partial/plain-text fallback, upload endpoint, frontend upload/preview support, and deterministic converter-double tests. Docling was not installed in the active environment, so live conversion was not claimed.

2026-10-04 Phase 3 hardening: bounded document uploads to 25 MiB, validated declared MIME types and PDF/OOXML signatures, fixed Windows temporary-file reopening, added real Docling PDF/DOCX/PPTX fixtures with page/slide assertions, and confirmed the Next.js build succeeds outside the sandbox. Final backend suite: 55 passed.

2026-10-04 Phase 4 image OCR: added bounded and signature-validated image ingestion, Docling-first OCR blocks, controlled PyTesseract fallback with timeout/availability handling, OCR bounding-box provenance, `/api/v1/sources/image`, and eight focused regression tests. No image frontend lifecycle or scanned-PDF OCR was added.

2026-10-04 Phase 5 audio ingestion: added optional Faster-Whisper audio transcription, bounded size/duration checks, CPU INT8 defaults, VAD and optional word timestamps, language and segment provenance, timeout/silent/runtime failure handling, `/api/v1/sources/audio`, and seven focused regression tests. Speaker diarization and frontend lifecycle work remain out of scope.
# MongoDB foundation slice

- Replaced the planned relational persistence direction with MongoDB.
- Added `MONGO_URI`, `MONGO_DATABASE`, and server-selection timeout settings.
- Added an async PyMongo client lifecycle boundary and initial workspace/source/extraction indexes under `app/storage/mongodb.py`.
- Removed duplicate Pydantic fields, corrected the `httpx` dependency name, and aligned the Docker runtime with the Python syntax used by the backend.
- Added fake-database regression tests. No live MongoDB connection was attempted in this slice.
- Verification: `pytest tests` passed with 23 tests; frontend TypeScript check passed.

# MongoDB document and repository slice

- Added explicit `SourceDocument` and `ExtractionDocument` contracts with workspace identifiers and UTC timestamps.
- Added a workspace-scoped `MongoRepository` and initial source/extraction listing boundary.
- Added optional FastAPI lifespan initialization guarded by `MONGO_ENABLED=false` by default; enabled mode pings MongoDB and creates indexes at startup.
- Verification: `pytest tests` passed with 25 tests; frontend TypeScript check passed; API imports successfully with MongoDB disabled.

# Phase 1 — canonical source model

- Added `app/source/models.py` with validated source types, processing statuses, content types, source locators, content units, extraction metadata, and `CanonicalSource`.
- Reused the canonical source model from `app/storage/schemas.py` instead of keeping a duplicate source document model.
- Added provenance, ordering, source-ownership, unique-ID, and range validation.
- Added serialization/deserialization and invalid-data regression tests in `tests/test_canonical_source.py`.
- Added schema documentation and illustrative JSON examples in `docs/engineering/CANONICAL_SOURCE_MODEL.md`.
- Phase 2+ integrations were not implemented.

# Phase 2 — WhatsApp ingestion

- Added dependency-free `app/ingestion/whatsapp.py` with Android/iOS-style timestamp recognition, sender extraction, multiline preservation, system/media/deleted classification, warnings, and partial extraction status.
- Converted parsed messages into the Phase 1 `CanonicalSource`/`ContentUnit` model with message-index and line-range provenance.
- Added `POST /api/v1/sources/whatsapp` without database persistence or provider changes.
- Integrated parsed source previews into the active Next.js page and added runtime response validation in `frontend/src/lib/api.ts`.
- Added synthetic parser and endpoint tests in `tests/test_whatsapp_ingestion.py`.
- Verification: `pytest tests` passed with 39 tests; TypeScript check passed; ESLint passed for modified frontend files.
- Phase 3+ integrations were not implemented.

# Groq structured-output diagnostics — 2026-10-04

- Confirmed Groq `json_validate_failed` on `openai/gpt-oss-20b` was a structured-output contract failure, with a separate confirmed completion truncation at the former 4096-token cap.
- Updated the Groq request to `max_completion_tokens=8192` with low reasoning effort, retained best-effort JSON Schema, and added safe error/finish-reason metadata logging.
- Made claim evidence required so Gemma cannot silently omit evidence and reach deterministic evidence validation with an empty list.
- Added provider and endpoint regression coverage for schema errors, truncation, local validation, current request fields, and omitted Gemma evidence.
- Live synthetic-chat verification produced a locally validated Groq result; later repeated probes were rate-limited by the Groq account TPM limit.

# Correlation c77b2c1bf36b follow-up — 2026-10-04

- Backend log review showed two independent failures: Gemma exceeded the 45-second local people-extraction budget, and Groq supplied evidence that did not resolve to the source.
- Added a bounded people-only Gemma output budget, correlation-scoped provider metadata logs, and one strict corrective Groq retry for evidence validation failures.
- Unsupported evidence is still rejected; the retry may only return a claim after the existing locator validation succeeds.

