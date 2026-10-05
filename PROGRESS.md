# Progress

Structured intelligence Phases 3–6 are implemented: typed categories now carry backend-generated evidence locators, unsupported evidence is rejected, and the frontend renders category sections, empty states, expandable evidence, uncertainty, and contradiction sides/resolution. Focused backend tests pass after the test expectation correction. Long synthetic-chat inference remains a runtime limitation requiring chunking.

Frontend runtime TypeError fixed at the API boundary: partial successful responses now receive empty arrays only for missing optional categories, while malformed required data fails visibly with a classified error.

Inference 503 root cause is documented and fixed at the retry/error-contract layer. Short live inference succeeds; full-chat runtime remains a known single-request limitation.

Groq fallback is implemented but opt-in: set the backend environment variables and enable the frontend consent checkbox to send a failed local source to Groq. Live Groq inference is not claimed because no valid key was available.

Long inputs now use message-boundary chunking up to the safety ceiling, with partial-result visibility. Cross-chunk semantic contradiction resolution remains limited to claims surfaced by individual chunks.

Groq fallback is live-verified with the provided key using `openai/gpt-oss-20b`; the frontend now transitions automatically after local timeout without showing a per-extraction consent checkbox.

Milestone A is complete. The first MongoDB foundation slice is present: configuration, dependency declaration, async client lifecycle boundary, initial indexes, and fake-database tests. Inference behavior remains unchanged.

Inference configuration uses `gemma4:e4b` primary and `gemma4:e2b` fallback. Ollama tags are verified, and five deterministic contract tests pass. Full frontend lint and build remain blocked; see `docs/tracking/TESTING.md`.

Phase 3 document ingestion is implemented: PDF, DOCX, and PPTX uploads now map through Docling into the canonical source/provenance model, with explicit dependency, validation, and partial-extraction states. Live Docling conversion is pending installation in the current environment.

Phase 3 regression hardening is complete: document uploads are bounded to 25 MiB, signatures and MIME types are checked, Windows temporary-file handling is fixed, real Docling conversion verifies PDF page and PPTX slide provenance, and the complete backend suite passes 55 tests. Next.js production build passes outside the sandbox; sandbox `spawn EPERM` is environmental.

Phase 4 image OCR is implemented: PNG/JPEG/WEBP/BMP/TIFF uploads are bounded and validated, Docling is attempted first, and PyTesseract is a controlled optional fallback. OCR blocks preserve available bounding boxes and explicit partial/failed states.

Phase 5 audio ingestion is implemented: optional Faster-Whisper emits timestamped transcript segments with language and word metadata, bounded by 50 MiB and 30 minutes, with CPU INT8/VAD defaults and explicit timeout/silent/runtime failures. No diarization was added.

Groq failure investigation is complete: the former 4096-token request could truncate GPT-OSS output, while best-effort schema validation also rejected overlarge/non-canonical generations. Groq now uses the current completion-token field, bounded 8192 output, low reasoning, explicit canonical-key prompts, and safe diagnostic metadata. Gemma claims require evidence at the Pydantic boundary. Focused regression tests pass; live verification succeeded once before the account TPM limit was reached.

Correlation `c77b2c1bf36b` follow-up is complete: Gemma's local timeout is mitigated with a bounded people-only output budget, and Groq evidence-validation failures now receive one corrective retry without weakening source matching or provenance checks.
