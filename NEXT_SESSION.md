# Next session

Install `requirements.txt`, run the provider and full test suites, then add mocked tests covering primary success, unavailable/malformed primary fallback, both failures, invalid fallback output, and no fallback for request validation. Verify the installed Ollama tags with `ollama list` without downloading models automatically.

Current blockers: repair remaining legacy frontend lint errors, investigate Windows Next.js TypeScript worker `spawn EPERM`, and isolate the legacy `test_backend.py` script that assumes a missing WhatsApp export.

After Phases 3–6, next recommended feature: deterministic long-source chunking with source-preserving aggregation, followed by a full synthetic WhatsApp regression run and frontend lint cleanup.

The latest frontend crash was fixed by runtime parsing in `frontend/src/lib/api.ts`; verify the browser with the synthetic WhatsApp chat after restarting the dev server.

Latest inference investigation: both Ollama models are installed and reachable. E4B timeout plus E2B truncated output caused the 503; categorized retry suppression and correlation IDs are now active. Next feature remains long-source chunking, outside this bug-fix scope.

Groq fallback is now present. Before demo use, configure `GROQ_API_KEY`, set `CLOUD_FALLBACK_ENABLED=true`, restart the backend, enable the consent checkbox, and test with a valid key. Do not log or commit the key.

Long-input support is implemented with WhatsApp chunking and partial metadata. Next recommended work is a dedicated cross-chunk reconciliation pass for semantic contradictions and a live Groq smoke test with a rotated key.

Groq smoke test now passes. The UI no longer asks per extraction; rotate the exposed key after this session, then configure it outside the repository before future runs.

Continue MongoDB integration by adding explicit source, extraction, and workspace document schemas plus repository methods. Wire the client through FastAPI lifespan only after the runtime dependency is installed and add a readiness check that reports MongoDB availability without blocking inference.

Phase 3 follow-up: install `requirements.txt` to enable Docling, then run a live PDF/DOCX/PPTX smoke test through `POST /api/v1/sources/document`. Keep MongoDB persistence and inference integration for later phases.

Phase 3 validation is now complete. Before image OCR, preserve the 25 MiB upload limit and signature validation, and keep the external-build invocation available on Windows environments where sandbox worker creation returns `spawn EPERM`.

Phase 4 is implemented and focused tests pass. Next work should verify the image endpoint with real user screenshots and an installed Tesseract executable before expanding to audio ingestion.

Phase 5 is implemented with optional Faster-Whisper dependencies. Before Phase 6, install `requirements-audio.txt` in an audio-enabled environment and run a real short voice-note smoke test; the current test suite uses deterministic transcriber doubles because Faster-Whisper is not installed.

Latest Groq investigation is complete. Keep `strict:false` for the existing generated schema, retain local Pydantic and evidence validation, and use `max_completion_tokens` rather than deprecated `max_tokens`. The remaining live limitation is the Groq account TPM rate limit; avoid repeated full-chat probes in quick succession.

Correlation `c77b2c1bf36b` is addressed. Monitor the new `AI_PEOPLE_MAX_OUTPUT_TOKENS` setting and the corrective Groq evidence retry during the next synthetic-chat smoke test; unsupported evidence must continue to produce a partial/controlled failure rather than being accepted.
