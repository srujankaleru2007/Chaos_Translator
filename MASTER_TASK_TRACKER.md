# Master task tracker

- [x] Configure Gemma 4 E4B as primary and E2B as fallback defaults.
- [x] Add environment-variable overrides and bounded retry/fallback flow.
- [x] Preserve strict shared Pydantic extraction validation.
- [x] Add Ollama setup and verification documentation.
- [ ] Install dependencies and run the full automated suite.
- [ ] Add mocked fallback matrix tests once the test environment is provisioned.
- [ ] BUG-001 (HIGH): Align the configured fallback model with the installed Ollama tag and verify fallback activation.
- [ ] BUG-002 (HIGH/MEDIUM): Reconcile the stale `/analyze` frontend client with the registered API contract.
- [ ] BUG-003 (MEDIUM): Resolve the 29 frontend lint errors and re-run the lint gate.
- [ ] SUS-001/SUS-002: Capture sanitized browser/backend evidence for the historical 422 and 503 before assigning exact historical root causes.
