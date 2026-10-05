# Bug tracker

## Remediation status — 2026-10-04

| ID | Status | Severity | Finding |
|---|---|---|---|
| BUG-001 | Fixed in code/config; live tags verified | High | E4B/E2B defaults are aligned. |
| BUG-002 | Fixed | High/Medium | Frontend uses one JSON `/api/v1/inference/test` client. |
| BUG-003 | In progress | Medium | Legacy frontend components still produce 29 lint errors. |
| BUG-004 | Fixed | Medium | Blank and 30,000-character validation exists client and server side. |
| BUG-005 | Fixed | Medium | Provider failures are categorized and 503 details are sanitized. |
| BUG-006 | Fixed | Medium | Remote Google Font dependency removed from layout. |

Remaining blockers: legacy lint errors, Windows Next.js `spawn EPERM`, and missing production auth/isolation.
## 2026-10-04 updates

- Fixed: typed claims now require source-supported evidence and receive deterministic line/message locators.
- Fixed: frontend no longer hides typed categories behind the legacy `items` list.
- Open: full synthetic WhatsApp inference can exceed the current 180-second test window; chunking is the next recommended feature.
- Open: legacy frontend lint failures and Windows Next.js worker `spawn EPERM` remain.

## Frontend runtime TypeError — 2026-10-04

- Root cause: `extractIntelligence()` used `payload as ExtractionResult`, which performs no runtime validation. A successful but partial response could leave `result.people` or another category undefined; the active page then evaluated `claims.length` and `claims.map`.
- Fix: added `parseExtractionResult()` at the API boundary. Missing optional category arrays normalize to empty arrays; required fields and malformed claims/evidence are rejected with a classified malformed-response error.
- Scope: active `Home` path and API client only; unrelated legacy components were not changed.

## Inference HTTP 503 — 2026-10-04

- Root cause: large structured requests exhausted E4B's 120-second generation attempts; E2B then returned truncated JSON. The route retried every failure category, so one request could spend over five minutes before returning 503.
- Confirmed not the cause: Ollama connectivity, missing model tags, request validation, or evidence validation. Both `gemma4:e4b` and `gemma4:e2b` were installed and `/api/tags` was healthy.
- Fix: retries now apply only to transient transport/protocol failures; timeout, truncation, invalid structured output, and evidence validation immediately activate the fallback model. 503 responses expose safe categories and a correlation ID, while logs retain detailed category/model/attempt data.
- Limitation: the full synthetic chat still exceeds the single-request runtime by design; chunking is intentionally out of scope for this bug fix.

## Groq fallback — 2026-10-04

- Added opt-in cloud fallback after the shared 45-second local budget.
- Cloud transmission requires both `CLOUD_FALLBACK_ENABLED=true` and request-level `cloud_consent=true`.
- API key remains backend-only; disabled/consent-missing paths do not instantiate or call Groq.
- Live Groq credentials were not available, so live cloud inference remains unverified.

## Long-input support — 2026-10-04

- Removed the 30,000-character API/frontend limit and replaced it with a documented 200,000-character safety ceiling.
- Added WhatsApp message-boundary chunking with multiline preservation and partial-result metadata.
- Failed chunks are returned in `failed_chunks`; partial output is not marked complete.

## Groq live verification — 2026-10-04

- Root cause: project Python requests received HTTP 403 until an explicit `User-Agent` was added; the original 120B model also failed structured generation for this workload.
- Fix: added `User-Agent: chaos-translator/0.1`, switched the default to `openai/gpt-oss-20b`, and added a separate 4096-token Groq budget.
- Live verification: HTTP 200 with `cloud_fallback_used=true` after local timeout.

## Phase 3 document ingestion — 2026-10-04

- Added a Docling-backed upload boundary for PDF, DOCX, and PPTX.
- Canonical content units preserve reading order and available page/character provenance.
- Missing Docling is surfaced as HTTP 503; unsupported extensions are HTTP 422; empty documents remain failed without fabricated content.
- Live conversion is pending installation of the declared Docling and multipart dependencies. Converter-double and endpoint regression tests pass.

## Phase 3 upload and live-conversion hardening — 2026-10-04

- Fixed a confirmed Windows bug where Docling could not reopen an in-use `NamedTemporaryFile`; temporary files are now closed before conversion and removed in `finally`.
- Added a 25 MiB bounded upload read, PDF/OOXML signature validation, and meaningful MIME validation.
- Real Docling conversion now passes for generated PDF, DOCX, and PPTX fixtures; PDF page and PPTX slide provenance are asserted.
- The first sandboxed Next.js build failed with `spawn EPERM`; the same Webpack build passed outside the sandbox, confirming an environment execution-policy issue rather than application code.

## Groq structured-output failure and Gemma evidence validation — 2026-10-04

- Root cause 1: Groq `json_validate_failed` was caused by best-effort schema validation against a model response that could exceed category cardinality or omit canonical fields. Separate live probes also confirmed the original 4096 completion cap could truncate generation; this was not solely a full-input-size issue.
- Root cause 2: Gemma's claim `evidence` field used a default empty list, so omitted evidence passed Pydantic and was rejected later by deterministic evidence validation.
- Fix: require at least one evidence reference on every claim, use Groq's current `max_completion_tokens` field with the configured 8192 budget and low reasoning effort, tighten the Groq prompt's canonical keys/cardinality, and retain local Pydantic/evidence validation. Groq strict mode was not enabled because the existing generated schema is not strict-compatible and strict probes exposed required-field/cardinality failures.
- Safe diagnostics now record provider error code/type, finish reason, usage, generated length, JSON validity, top-level keys, and category counts without logging source text, generated content, or credentials.
- Verification: focused provider/contract/structured-intelligence tests pass; one live synthetic-chat Groq call produced a validated result, and a subsequent probe hit the account's Groq TPM rate limit (429), which remains an external limitation.

## Correlation c77b2c1bf36b — local timeout and Groq evidence validation — 2026-10-04

- Confirmed from backend logs: Gemma hit the 45-second local budget (`local_timeout`), while Groq independently failed deterministic `evidence_validation`; neither failure was converted into an accepted unsupported claim.
- Fix: bound the people-only Gemma response budget with `AI_PEOPLE_MAX_OUTPUT_TOKENS=768`, add correlation-scoped safe metadata logging, and retry Groq once only with a corrective evidence instruction. Evidence remains required and must match a contiguous source quote before provenance is generated.
- Regression coverage verifies local timeout produces a partial result, unsupported Groq evidence is retried, and only the corrected source-grounded claim is returned.
