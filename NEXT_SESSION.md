# Next session

Install `requirements.txt`, run the provider and full test suites, then add mocked tests covering primary success, unavailable/malformed primary fallback, both failures, invalid fallback output, and no fallback for request validation. Verify the installed Ollama tags with `ollama list` without downloading models automatically.

Current blockers: repair remaining legacy frontend lint errors, investigate Windows Next.js TypeScript worker `spawn EPERM`, and isolate the legacy `test_backend.py` script that assumes a missing WhatsApp export.
