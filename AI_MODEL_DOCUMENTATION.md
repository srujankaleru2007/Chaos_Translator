# AI model configuration

The default local setup uses Ollama with `gemma4:e4b` as the primary model and `gemma4:e2b` as the fallback. Both responses use the same `ExtractionResult` Pydantic schema and Ollama JSON-schema output format.

Environment variables:

```env
AI_PROVIDER=ollama
AI_PRIMARY_MODEL=gemma4:e4b
AI_FALLBACK_MODEL=gemma4:e2b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT_SECONDS=120
AI_RETRIES=1
AI_MAX_OUTPUT_TOKENS=2048
```

Install only after confirming the tags available to your Ollama installation:

```powershell
ollama list
ollama pull gemma4:e4b
ollama pull gemma4:e2b
```

The API retries the primary model, validates its JSON with Pydantic, and then tries the fallback after exhausted provider, availability, resource, or structured-output failures. User-input validation errors do not enter this flow. Run `python -m unittest tests.test_provider -v` after installing project dependencies. Change models by changing the environment variables; no provider code changes are required.
