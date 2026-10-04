# AI model configuration

The local inference contract uses Ollama with `gemma4:e4b` as primary and `gemma4:e2b` as fallback. Both use the same `ExtractionResult` Pydantic schema and JSON Schema output format. Provider failures are categorized, bounded retries are applied, and fallback is attempted only after provider failure—not request validation failure.

Configured variables: `AI_PROVIDER`, `AI_PRIMARY_MODEL`, `AI_FALLBACK_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT_SECONDS`, `AI_RETRIES`, and `AI_MAX_OUTPUT_TOKENS`.
## Structured extraction contract

Gemma receives category-specific instructions for people, tasks, deadlines/events, decisions, unanswered questions, technical issues, dependencies, and contradictions. It must provide exact evidence quotes and may not invent ownership, dates, statuses, resolutions, IDs, timestamps, or page numbers. The backend treats model evidence references as untrusted: it matches quotes against the source and generates source ID, line range, WhatsApp message index, and timestamp deterministically.
