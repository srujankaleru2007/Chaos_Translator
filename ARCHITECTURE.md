# Inference architecture

`app.core.config.Settings` centralizes provider, model, retry, timeout, and output-token settings. `OllamaProvider` owns `/api/tags` availability checks and `/api/chat` structured generation. `app.api.routes` applies the bounded primary-then-fallback policy and passes the same schema and prompt contract to both models.

Responses are never accepted without strict Pydantic validation. Ollama receives the generated JSON schema and a configurable `num_predict` limit to reduce structured-output truncation. The hosted-provider boundary remains configurable through `AI_PROVIDER`; the current implementation is Ollama-focused.
