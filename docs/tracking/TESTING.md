# Testing record

- Ollama tags verified: `gemma4:e4b`, `gemma4:e2b`.
- Added and installed `pytest` and `httpx2`.
- `pytest -q tests/test_inference_contract.py`: **5 passed**.
- Coverage includes blank input, length limits, missing fields, incorrect types, primary success, fallback success, and safe 503 behavior.
- `npm run lint`: still fails with 29 errors and 16 warnings in legacy components.
- `npm run build`: compiles successfully, then fails during TypeScript worker startup with Windows `spawn EPERM`.
## Structured intelligence regression

Focused command:

`\.venv\Scripts\python.exe -m pytest -q tests/test_inference_contract.py tests/test_provider.py tests/test_structured_intelligence.py`

Coverage includes typed category validation, exact evidence matching, deterministic line locators, rejection of unsupported evidence, empty categories, provider fallback, and safe API failures. The latest run passed after correcting a test that expected a model-supplied message index; backend code correctly ignores that fabricated locator and generates its own.

The complete 6,187-byte synthetic WhatsApp chat remains an open runtime test because the current single-request inference path exceeded 180 seconds. This is a performance limitation, not a passing regression result.
