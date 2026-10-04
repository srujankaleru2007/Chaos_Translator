# Inference architecture

The active frontend calls one reusable JSON client, which sends `{text, source_type}` to `POST /api/v1/inference/test`. FastAPI validates input, then applies bounded primary/fallback selection through `OllamaProvider`. Ollama receives the Pydantic-generated JSON Schema; the response is validated before it is returned. Provider failures are categorized and exposed to the client only through safe aggregate error details.
