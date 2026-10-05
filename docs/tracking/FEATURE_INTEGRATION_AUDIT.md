# The Chaos Translator — Feature Integration Audit

Status: audit and planning only. No source code, dependency, or architecture changes were made for this audit.

## 1. Existing project architecture

### Active product path

- `frontend/src/app/page.tsx` is the active Next.js intake/results page. It accepts text or `.txt`, `.md`, and `.csv` files and renders the eight structured intelligence categories.
- `frontend/src/lib/api.ts` is the active JSON client for `POST /api/v1/inference/test`. It validates required response fields and normalizes genuinely optional category arrays.
- `app/main.py` creates the FastAPI application, CORS policy, health endpoint, and optional MongoDB lifespan.
- `app/api/routes.py` owns inference orchestration, WhatsApp chunk splitting, provider fallback, evidence locator generation, evidence validation, and chunk aggregation.
- `app/inference/schemas.py` defines `ExtractionRequest`, `ExtractionResult`, typed claim categories, and `EvidenceRef`.
- `app/inference/provider.py` contains the existing Ollama and Groq adapters. Provider selection/model work is intentionally out of scope for this audit.
- `app/inference/chunking.py` provides WhatsApp message-boundary chunking.
- `app/storage/schemas.py` and `app/storage/mongodb.py` are the new MongoDB persistence boundary. MongoDB startup is disabled by default and is not yet connected to inference writes.

### Legacy Chatlytics path

- `app/preprocess.py` contains a pandas/dateutil WhatsApp-to-DataFrame parser.
- `app/analytics.py`, `app/topics.py`, and `ml/` contain the original analytics, sentiment, topic, role, anomaly, and visualization support.
- `frontend/src/components/UploadSection.tsx` and the dashboard components represent the older analytics UI. `UploadSection` calls the current extraction helper but is not imported by the active `page.tsx`.
- `README.md` and the legacy tests still describe the original Chatlytics multipart/analytics product.

### Reusable assets

- Existing `EvidenceRef` already has the core provenance fields: source ID, message index, line range, timestamp, and page number.
- Existing `ExtractionResult` is the correct downstream intelligence contract. New adapters should produce normalized source units, not separate intelligence pipelines.
- Existing Pydantic validation, frontend runtime parsing, and evidence matching should remain intact.
- Existing `preprocess.py` has useful WhatsApp intent but is DataFrame-oriented and loses some source-location semantics. It should be adapted behind a normalized adapter instead of duplicated.

### Redundant or retiring areas

- The legacy `/analyze` multipart flow is not registered by the backend. It should be retired only after confirming no supported page still depends on it.
- Analytics such as word clouds, sentiment, and activity statistics are not the core cross-source intelligence product. Preserve them as optional legacy views, but do not make them dependencies of the normalized ingestion path.
- Do not maintain separate WhatsApp, document, image, and audio extraction result models.

## 2. Reference repository audit

### WhatsApp Chat Analyzer

Verified capabilities include automatic iOS/Android format detection, locale-aware date parsing, 12/24-hour time handling, multiline messages, typed text/media/system/deleted messages, media subtypes, system-message handling, filters, anonymization, statistics, and JSON/CSV/DataFrame export. It is standard-library-first, Python 3.10+, and MIT licensed.

Recommended reuse: adapt its parser concepts or use the package behind a project-owned adapter that emits normalized source units. Preserve raw text and exact line/message offsets before applying filters or anonymization. Do not import its analytics reports into the intelligence model.

Compatibility risk: date ambiguity, localized system messages, media placeholders, BOMs, and multiline continuation lines must be tested against the supplied synthetic chat and Android/iOS fixtures.

### Docling

Verified capabilities include PDF, DOCX, PPTX, image, plain-text, audio and many other formats; layout and reading order; tables; headings/sections; unified `DoclingDocument`; Markdown/HTML/WebVTT/lossless JSON export; page-aware document processing; local execution; and OCR support for scanned documents.

Recommended reuse: use Docling as the primary document adapter for PDF, DOCX, PPTX, and image/document inputs. Keep its page/block/table structure long enough to create page and block locators, then emit normalized source units. Prefer local execution for privacy.

Compatibility risk: large dependency footprint, model downloads, platform-specific OCR/runtime behavior, and conversion quality differences between born-digital and scanned files. Pin and test the exact version before adding it to the base dependency set.

### PyTesseract

Verified capabilities include plain OCR, language selection, timeout handling, bounding boxes, confidence/page metadata through `image_to_data`, orientation/script detection, searchable PDF/HOCR/ALTO output, and multiple outputs in one invocation.

Recommended reuse: keep it as an explicit OCR fallback or diagnostic adapter when Docling cannot process a raster image or when bounding-box-level data is required. Do not run it in parallel with Docling by default.

Compatibility risk: it is a Python wrapper, not the Tesseract engine. The native Tesseract executable and language data must be installed separately. It is Apache-2.0; retain its license/notice if code is copied.

### Faster-Whisper

Verified capabilities include audio transcription, language detection/probability, timestamped segments, optional word timestamps, VAD filtering, CPU INT8 and GPU execution, batched transcription, and long-audio generator-based processing. PyAV bundles FFmpeg decoding for the standard installation. GPU deployments require compatible CUDA/cuDNN versions.

Recommended reuse: use it as the audio/voice-note adapter. Emit one normalized source unit per segment, with optional word-level metadata and timestamp ranges. Iterate the segment generator fully and enforce duration, size, and timeout limits.

Compatibility risk: model downloads and memory use, CPU latency, CUDA/cuDNN compatibility, language accuracy, and speaker diarization being outside the core package. Speaker identity should remain optional and unclaimed unless a separate diarization capability is added.

## 3. Current versus missing feature matrix

| Capability | Current project | Reference capability | Recommendation |
|---|---|---|---|
| WhatsApp raw text intake | Partial | Robust parser | Integrate/adapt first |
| Android/iOS/date formats | Partial regex parser | Automatic detection and locale handling | Replace parser internals behind adapter |
| Multiline/system/media messages | Partial | Typed message handling | Integrate |
| PDF/DOCX/PPTX | Missing | Docling | Integrate after common schema |
| Scanned PDF/image OCR | Missing | Docling OCR | Integrate with page provenance |
| OCR fallback/bounding boxes | Missing | PyTesseract | Add only as explicit fallback |
| Audio/voice notes | Missing | Faster-Whisper | Integrate after common schema |
| Typed intelligence | Present | Not provided by references | Preserve existing model |
| Evidence references | Present but text/line focused | Page/time/box metadata available upstream | Extend `EvidenceRef` carefully |
| Cross-source linking | Missing | Not provided directly | Implement independently after ingestion |
| MongoDB persistence | Boundary present | Not provided by references | Wire after normalized source contract |
| Legacy analytics | Present | Not required | Preserve as optional/retire gradually |

## 4. Unified normalized source representation

Use one project-owned model rather than exposing library-specific objects downstream:

```text
SourceDocument
  id
  workspace_id
  source_type: whatsapp | pdf | docx | pptx | image | audio | text
  filename
  media_type
  raw_text_or_reference
  metadata
  extraction_status
  warnings[]
  units[]

SourceUnit
  id
  ordinal
  text
  source_locator
  timestamp_start / timestamp_end
  speaker_or_sender
  page_number
  message_index
  segment_index
  bounding_box
  metadata
```

The source locator must be typed, for example `whatsapp_message`, `document_page`, `document_block`, `image_region`, or `audio_segment`. The intelligence pipeline consumes `SourceUnit` text and carries the locator into `EvidenceRef`; it must never reconstruct provenance from only a flattened summary.

## 5. Dependency-ordered implementation plan

### Phase 1 — Canonical source model and adapter contract

Files: `app/storage/schemas.py`, new `app/ingestion/`, `app/inference/schemas.py`, tests.

Implement the normalized document/unit models, typed locators, warning/status model, and adapter protocol. Keep existing `ExtractionResult` as the downstream contract. Add serialization tests and evidence round-trip tests.

Acceptance: a text source and the current synthetic WhatsApp source can be represented without losing exact source positions.

### Phase 2 — WhatsApp ingestion improvements

Files: new `app/ingestion/whatsapp.py`, existing `app/preprocess.py`, chunking tests.

Adapt the verified parser capabilities: iOS/Android detection, locale-aware dates, multiline handling, system/media/deleted message types, filters, and optional anonymization. Preserve unmodified source text and line/message locators.

Acceptance: Android, iOS, multiline, system, media, malformed-line, BOM, locale-ambiguity, and anonymization tests pass; synthetic chat maps deterministically.

### Phase 3 — Document ingestion with Docling

Files: new `app/ingestion/documents.py`, dependency lock/config, document fixtures/tests.

Add PDF, DOCX, and PPTX ingestion using a pinned Docling version. Preserve page, block, table, heading, and reading-order metadata. Scanned inputs must report OCR warnings rather than silently returning empty text.

Acceptance: born-digital and scanned fixtures produce normalized units with page references and warnings.

### Phase 4 — Image and screenshot OCR

Files: new `app/ingestion/images.py`, OCR adapter tests.

Use Docling OCR first. Add PyTesseract only as a controlled fallback for unsupported images or bounding-box needs, with executable/language availability checks and timeouts.

Acceptance: image text, region coordinates when available, OCR failure status, and privacy-safe errors are covered.

### Phase 5 — Audio and voice-note ingestion

Files: new `app/ingestion/audio.py`, audio fixtures/tests, optional dependency group.

Integrate Faster-Whisper with segment timestamps, language metadata, optional word timestamps, VAD, duration/size limits, and CPU-safe defaults. Do not add speaker diarization in this phase.

Acceptance: short audio, long audio, silent audio, unsupported format, timeout, language detection, and timestamp provenance tests pass.

### Phase 6 — MongoDB persistence and retrieval

Files: `app/storage/schemas.py`, `app/storage/mongodb.py`, new repositories/routes, MongoDB integration tests.

Persist normalized source documents, extraction results, warnings, and provenance. Require workspace scope in repository methods. Add retrieval endpoints only after an authentication/workspace identity decision.

Acceptance: source and extraction documents round-trip through MongoDB, indexes are used, and no raw BSON types leak through API responses.

### Phase 7 — Cross-source intelligence

Files: inference service layer, aggregation/reconciliation modules, evidence tests.

Run one downstream intelligence pipeline over multiple normalized sources. Add cross-source entity, task, decision, dependency, contradiction, and evidence linking. Preserve source IDs and locators for every claim.

Acceptance: two documents and one chat can produce linked claims with evidence from each source; contradictory claims remain distinguishable and traceable.

### Phase 8 — Frontend source lifecycle

Files: `frontend/src/app/page.tsx`, `frontend/src/lib/api.ts`, new source/status components.

Add file-type acceptance, upload status, warnings, source navigation, evidence navigation, and partial extraction states. Retire the stale multipart path only after confirming it is unused.

Acceptance: each supported source type has a visible status, failures do not destroy previous results, and evidence opens the correct source locator.

### Phase 9 — Validation and regression suite

Files: `tests/`, frontend contract tests, fixtures, `docs/tracking/TESTING.md`.

Add adapter contract tests, golden fixtures, malformed input tests, provenance tests, cross-source tests, and browser-level regression coverage.

Acceptance: all adapters satisfy the same contract and no category or evidence reference disappears during normalization.

## 6. Licensing and attribution

- Existing project: MIT, copyright Alex 2026.
- WhatsApp Chat Analyzer: MIT.
- Docling: MIT.
- Faster-Whisper: MIT.
- PyTesseract: Apache-2.0. If reused or redistributed, retain the Apache license, copyright/attribution notices, and any applicable NOTICE text; do not use project trademarks as if endorsed.
- Transitive dependencies and model checkpoints require separate license review. In particular, OCR language data and downloaded ASR/document models may have terms separate from the Python package.

Recommended: add `THIRD_PARTY_NOTICES.md` before the first dependency is installed, listing direct libraries, licenses, source URLs, pinned versions, and model/data notices. Do not copy whole repositories.

## 7. Risks and unresolved questions

1. Should source originals be stored in MongoDB, object storage, or only locally with a hash/reference?
2. What workspace/authentication identity is required before retrieval routes are exposed?
3. Which languages and WhatsApp locales must be supported in the first release?
4. Are audio files allowed to leave the local machine? This affects model/runtime and retention decisions.
5. What maximum file size, audio duration, PDF page count, and OCR timeout are acceptable?
6. Does the product require exact visual evidence regions, or are page/line/time locators sufficient for the first release?
7. Docling and Faster-Whisper are substantial optional dependencies; they should be installed in feature-specific environments rather than making the minimal text-only runtime unnecessarily heavy.

## 8. Audit conclusion

The correct integration strategy is adapter-first and provenance-first. Start with the canonical source model, then improve WhatsApp parsing, add Docling documents, use PyTesseract only as a bounded OCR fallback, add Faster-Whisper audio, and only then implement cross-source reconciliation and frontend expansion. Existing structured intelligence and evidence validation are valuable foundations and should not be replaced by library-specific models.
