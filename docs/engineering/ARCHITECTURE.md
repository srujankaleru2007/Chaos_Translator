# Inference architecture

The active frontend calls one reusable JSON client, which sends `{text, source_type}` to `POST /api/v1/inference/test`. FastAPI validates input, then applies bounded primary/fallback selection through `OllamaProvider`. Ollama receives the Pydantic-generated JSON Schema; the response is validated before it is returned. Provider failures are categorized and exposed to the client only through safe aggregate error details.
## Inference provider policy

The API executes one shared extraction pipeline with explicit task routing. Local Ollama Qwen 3.5 4B is used only for the `people` category, with a narrow people-only Pydantic schema and deterministic evidence validation. Groq handles tasks, deadlines, decisions, questions, technical issues, dependencies, contradictions, and cross-source reasoning directly. The legacy `cloud_consent` request field remains accepted for compatibility but does not gate this configured server-side route.

The configured Qwen model is available for local diagnostics and people extraction only. Groq failures are categorized and returned as controlled 503 responses; the pipeline never silently falls back from Groq to local Qwen for non-name categories.

Groq structured responses are requested with best-effort JSON Schema and validated locally. This preserves the existing Pydantic/evidence contract while avoiding strict-schema rejection of optional/defaulted claim fields. Provider logs retain only safe metadata such as error category, finish reason, usage, generated length, and top-level keys.

Persistence direction: MongoDB with the official PyMongo async API. The initial storage boundary defines one process-wide client and workspace/source/extraction indexes; route-level persistence will be added after authentication and workspace identity exist.
