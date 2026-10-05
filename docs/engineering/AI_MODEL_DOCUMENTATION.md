# AI model configuration

The inference contract is task-routed. Ollama `qwen3.5:4b` receives only a narrow `PeopleExtractionResult` schema for source-supported name extraction. Groq receives the full `ExtractionResult` schema for tasks, deadlines, decisions, questions, technical issues, dependencies, contradictions, and cross-source reasoning. `qwen3.5:4b` is retained as the configured health-check fallback identity and is not a separate generation fallback.

Configured variables: `AI_PROVIDER`, `AI_PRIMARY_MODEL`, `AI_FALLBACK_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT_SECONDS`, `AI_RETRIES`, and `AI_MAX_OUTPUT_TOKENS`.
## Structured extraction contract

Qwen receives a people-only instruction and cannot populate other categories through its response schema. It must provide exact evidence quotes and may not invent a person or role. Groq receives the remaining category instructions and may not invent ownership, dates, statuses, resolutions, IDs, timestamps, or page numbers. The backend treats model evidence references as untrusted: it matches quotes against the source and generates source ID, line range, WhatsApp message index, and timestamp deterministically.

## Provider fallback

Qwen name extraction and Groq intelligence extraction run as separate provider calls per chunk. Qwen uses a bounded people-only output budget (`AI_PEOPLE_MAX_OUTPUT_TOKENS`, default 768) so name extraction cannot spend the full general extraction budget. If Qwen fails but Groq succeeds, the response is marked partial and contains no unsupported people. If Groq is unavailable, the API returns a categorized 503; it never substitutes local Qwen for the non-name categories. Default local model: `qwen3.5:4b`; default Groq model: `openai/gpt-oss-20b`. Groq has a separate `GROQ_MAX_OUTPUT_TOKENS` budget, uses best-effort JSON Schema (`strict: false`) because the shared schema contains nullable/defaulted fields that are not strict-compatible, and is still checked locally by Pydantic plus deterministic evidence validation. The request uses `max_completion_tokens` and low reasoning effort. The API key is loaded only by the backend environment.
