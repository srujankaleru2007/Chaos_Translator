# Chaos Translator — Diagnostic Audit

**Audit date:** 2026-10-04 (Asia/Calcutta)  
**Scope:** Investigation only. No application code, dependencies, schemas, or runtime configuration were changed.

## Executive summary

The repository contains a working FastAPI inference path and a Next.js client path, but the local environment does not currently provide a healthy end-to-end developer run by default. Ollama is reachable and the primary model `gemma4:e4b` is installed and produced valid structured JSON. The configured fallback `gemma4:e2b` is absent; the installed alternative is `gemma4:e2b-it-q4_K_M`. Consequently, `/api/v1/health/ollama` returns HTTP 200 with `status: model_unavailable`, and fallback activation cannot succeed for the configured tag.

The reported HTTP 422 is reproducible when the request violates the Pydantic contract (empty `text`); it is not evidence of an Ollama failure. A valid request to the application endpoint succeeded through E4B. A 503 was not reproduced in this audit because E4B was available; source inspection shows it is emitted only after every configured model/attempt raises `ProviderError`.

The frontend has a separate stale API helper that posts multipart data to `/analyze`, a route that is not registered by the backend, although the currently rendered `page.tsx` uses the correct JSON endpoint. Frontend lint fails with 29 errors and 19 warnings. Production build fails in this environment while fetching Google Fonts through `next/font`, which is an environmental/build reproducibility issue unless the project intends to require network access at build time.

## Actual architecture overview

```text
Next.js app/page.tsx
  -> POST http://localhost:8000/api/v1/inference/test
     JSON {text, source_type}
  -> FastAPI app/main.py -> app/api/routes.py
     -> OllamaProvider.status() -> GET /api/tags
     -> OllamaProvider.generate_structured() -> POST /api/chat
     -> Pydantic ExtractionResult validation
  -> JSON response rendered in page.tsx
```

Implemented source includes FastAPI, a local Ollama provider, frontend intake/results UI, and unrelated `ml/` analytics modules. No database, migration, authentication/authorization, upload persistence, or background worker implementation was found in the source inventory. The Dockerfile exists, but no compose/orchestration configuration was found.

## Frontend audit

- `frontend/src/app/page.tsx:25-46` initiates the active inference request. It sends `POST /api/v1/inference/test` with JSON and correctly handles a string detail, the structured all-models-failed detail, and generic non-OK responses.
- `frontend/src/lib/api.ts:1-25` is a stale, currently unused client that sends multipart `POST /analyze`. No `/analyze` backend route exists. If this helper is used by the older `UploadSection` flow, it will fail with a route mismatch.
- `frontend/src/components/UploadSection.tsx:58-66` uses that stale helper and leaves `loading=true` on success; the component is not imported by the current `page.tsx` based on the current source graph.
- The active page accepts `.txt`, `.md`, and `.csv` but labels the source as `whatsapp` for every `.txt`; the backend accepts arbitrary `source_type` strings. No client-side 30,000-character limit is enforced, so oversized input reaches the backend as a 422.
- No duplicate request was reproduced from the active page source. There is no retry loop in the frontend.
- `npm run lint`: failed, 29 errors and 19 warnings. Representative blocking files: `AdvancedAnalytics.tsx`, `AnomalyPanel.tsx`, `Dashboard.tsx`, `MemoryGame.tsx`, `SentimentView.tsx`, and `UploadSection.tsx`.
- `npm run build`: failed before completion because `next/font` could not fetch Geist and Geist Mono from Google Fonts in this environment (`frontend/src/app/layout.tsx`).

## Backend audit

- `app/main.py:6-20` imports successfully, registers the router under `/api/v1`, and configures CORS for `http://localhost:3000`.
- `app/api/routes.py:30-45` defines the expected endpoint and performs bounded model/attempt iteration. A valid request was accepted and returned HTTP 200.
- `app/inference/schemas.py:16-18` requires `text` length 1–30,000. Empty text produced the exact 422 body: `string_too_short`, location `body.text`, minimum length 1.
- `app/inference/provider.py:78-107` uses Ollama `/api/chat`, `stream:false`, `think:false`, a Pydantic-generated JSON schema, and `model_validate_json`.
- Backend startup/import check passed under `.venv` Python 3.13.15. `/health` returned HTTP 200 while the temporary audit server was running.
- `pytest` could not run: `.venv` has no `pytest` module. This is an environment/test-provisioning failure, not a test pass.
- The 503 mapping in `app/api/routes.py:40-45` is broad by design: all provider errors, including missing model, network, timeout, HTTP, and output-validation failures, are flattened into one 503 detail structure after exhaustion.

## Ollama and Gemma audit

- Ollama API `http://127.0.0.1:11434/api/tags` was reachable.
- Installed tags observed: `gemma4:e4b` and `gemma4:e2b-it-q4_K_M`.
- E4B direct minimal JSON inference succeeded.
- Direct request to `gemma4:e2b` returned HTTP 404 (model not found).
- The application endpoint succeeded on E4B for `Rahul will prepare the presentation by October 8.` and returned a valid `ExtractionResult`.
- `/api/v1/health/ollama` returned HTTP 200 with `status: model_unavailable`, because the implementation treats either missing configured model as unavailable (`app/api/routes.py:18`).
- The provider performs a `/api/tags` request before each generation attempt (`provider.py:78-84`), adding latency and another failure point.
- No application 503 was reproduced. It remains a confirmed reachable code path, but the specific observed 503 cause is not proven by this run.

## API contract and error investigation

| Finding | Evidence | Classification |
|---|---|---|
| Empty text request | HTTP 422; `body.text`; `string_too_short`; `min_length: 1` | Reproduced validation behavior, not necessarily a bug |
| Valid JSON extraction | HTTP 200 through E4B with summary and empty items | Reproduced success |
| Missing fallback tag | `/api/chat` with `gemma4:e2b` returned HTTP 404; tags show only `gemma4:e2b-it-q4_K_M` | Confirmed bug/configuration defect |
| Backend unavailable at initial probe | Port 8000 refused before temporary uvicorn launch | Environmental/startup state |

The original browser 422 request body and timestamp were not available in this audit, so it cannot be proven that the browser's 422 was caused by empty input, oversized input, malformed JSON, or a different payload. The backend's precise validation behavior is confirmed above.

## Dependency and environment audit

- Python: 3.13.15 in the system and project `.venv`.
- `requirements.txt` contains only unpinned `fastapi`, `uvicorn`, and `pydantic`; there is no declared test dependency.
- Frontend dependencies are installed (`frontend/node_modules` exists); lockfile is present.
- `.env.example` disagrees with the code defaults for fallback: it specifies `gemma4:e2b-it-q4_K_M`, while `app/core/config.py:9` defaults to `gemma4:e2b`.
- Environment variable names found: `AI_PROVIDER`, `AI_PRIMARY_MODEL`, `AI_FALLBACK_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT_SECONDS`, `AI_RETRIES`, `AI_MAX_OUTPUT_TOKENS`, and `NEXT_PUBLIC_API_URL`. Values were not included in this report.
- Build requires access to Google Fonts because of `next/font`; that network dependency caused the observed build failure.

## Database and persistence audit

No database driver, ORM model, migration directory, connection/session setup, or persistence route was found in the source inventory. Failed inference requests therefore have no implemented database-record consistency behavior to audit.

## Testing results

| Check | Result |
|---|---|
| Python import / FastAPI route startup | Passed |
| `/health` | Passed, HTTP 200 |
| Ollama `/api/tags` | Passed, reachable |
| Direct E4B JSON inference | Passed |
| Direct E2B inference | Failed as expected: HTTP 404 missing tag |
| Application valid inference | Passed, HTTP 200 |
| Application empty-text request | Reproduced HTTP 422 |
| Application Ollama health | HTTP 200, `model_unavailable` |
| Pytest | Not run: module not installed |
| Frontend lint | Failed: 29 errors, 19 warnings |
| Frontend production build | Failed: Google Fonts fetch in `next/font` |

## Security and reliability findings

- **MEDIUM — R-001:** Inference timeout is 120 seconds by default and E4B cold start was approximately 51 seconds in the direct probe. A browser request can appear hung, and each fallback/attempt can multiply latency (`app/core/config.py:11-13`, `routes.py:34-44`).
- **MEDIUM — R-002:** Error responses include provider attempt strings and model names (`routes.py:45`). They do not expose secrets in the observed path, but details may reveal internal service topology and raw upstream error text.
- **MEDIUM — R-003:** No authentication or workspace isolation is implemented. This is acceptable for a local prototype but unsafe if exposed beyond localhost.
- **LOW — R-004:** Input size is enforced server-side but not before transmission in the active frontend, creating avoidable 422s for oversized pasted content.
- **INFORMATIONAL — R-005:** CORS is limited to localhost:3000, which is appropriate for the current local development target.

## Confirmed bugs

### BUG-001 — Configured fallback model is not installed

- **Severity:** HIGH
- **Component:** Ollama configuration/provider
- **Root cause:** Code default is `gemma4:e2b`, while installed fallback is `gemma4:e2b-it-q4_K_M`; `.env.example` already names the latter.
- **Evidence:** `/api/tags`; direct `gemma4:e2b` request returned 404; `app/core/config.py:9`; `.env.example:4`.
- **Impact:** Fallback cannot activate; health reports model unavailable whenever the default is used.
- **Recommended fix:** Align configured fallback with an actually installed tag, or provision the exact configured tag, then verify fallback behavior with the primary unavailable.

### BUG-002 — Stale frontend API client targets an unimplemented route

- **Severity:** HIGH if reachable; MEDIUM as current dead code
- **Component:** Frontend API integration
- **Root cause:** `frontend/src/lib/api.ts:8` posts multipart data to `/analyze`, but backend only registers `/api/v1/inference/test` and health routes.
- **Impact:** Any consumer of `analyzeChat` receives a route failure and mismatched payload contract.
- **Recommended fix:** Remove or reconcile the stale flow after confirming whether `UploadSection` is intentionally retired.

### BUG-003 — Frontend lint gate fails

- **Severity:** MEDIUM
- **Component:** Frontend quality/build pipeline
- **Evidence:** `npm run lint` produced 29 errors and 19 warnings, including a hook declaration-order error in `MemoryGame.tsx:53-107`.
- **Impact:** CI or release workflows using lint cannot pass.
- **Recommended fix:** Address lint errors with type-safe changes and verify behavior with tests.

## Suspected issues

- **SUS-001:** The reported browser 422 may be caused by empty/oversized input or malformed request data. The browser request body was not captured, so only backend validation outcomes are confirmed.
- **SUS-002:** The reported browser 503 may be a missing fallback, Ollama load/resource exhaustion, timeout, or invalid model output after primary failure. No 503 occurred while E4B was healthy, so the precise historical cause is unverified.
- **SUS-003:** Build failures may be network-policy-specific. `next/font` makes the build dependent on Google Fonts availability; this is a reproducible issue in the audited environment, but intent is unknown.

## Root-cause analysis

The strongest confirmed blocker is configuration drift between the code default and the installed Ollama fallback tag. The active primary path is healthy, so this does not explain every failed request. The 422 and 503 are separate classes: 422 is FastAPI request validation before provider invocation; 503 is emitted only after provider failures exhaust all model/attempt combinations. The report cannot responsibly collapse them into one root cause without the original browser request and backend traceback.

## Prioritised remediation plan

1. Resolve fallback tag ownership/configuration and add a mocked fallback matrix test.
2. Capture and preserve sanitized request/response logs for the actual browser failures.
3. Reconcile the stale `/analyze` client and active page flow.
4. Provision test tooling and add endpoint/provider contract tests.
5. Fix frontend lint errors, then make the production build independent of unavailable external font fetches if offline builds are required.
6. Reassess timeout, error-detail exposure, authentication, and resource limits before any non-local deployment.

## Recommended next development task

Create a test-only provider abstraction with mocked primary failure, fallback success, missing-model, malformed-output, and timeout cases; then verify the HTTP status/detail contract and frontend rendering for 422 and 503 without downloading models or modifying production behavior.

## Community Wisdom

Relevant developer reports broadly support the current use of Ollama's JSON-schema `format` plus Pydantic validation, while warning that smaller local models can still struggle with complex schemas and that retries should be explicit. This supports treating structured-output failures as a separately testable provider concern rather than hiding them behind a generic frontend message.

- [Clean JSON Extraction with Ollama and Python](https://dev.to/nearshi/-clean-json-extraction-with-ollama-and-python-21f3) — [nearshi](https://dev.to/nearshi)
- [Ollama Structured Outputs in Practice — Getting Type-Safe JSON from Local LLMs with Pydantic](https://dev.to/jangwook_kim_e31e7291ad98/ollama-structured-outputs-in-practice-getting-type-safe-json-from-local-llms-with-pydantic-m38) — [jangwook_kim_e31e7291ad98](https://dev.to/jangwook_kim_e31e7291ad98)
