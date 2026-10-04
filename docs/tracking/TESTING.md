# Testing record

- Ollama tags verified: `gemma4:e4b`, `gemma4:e2b`.
- Added and installed `pytest` and `httpx2`.
- `pytest -q tests/test_inference_contract.py`: **5 passed**.
- Coverage includes blank input, length limits, missing fields, incorrect types, primary success, fallback success, and safe 503 behavior.
- `npm run lint`: still fails with 29 errors and 16 warnings in legacy components.
- `npm run build`: compiles successfully, then fails during TypeScript worker startup with Windows `spawn EPERM`.
