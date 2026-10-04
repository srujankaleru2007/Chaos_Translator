# API reference

## `POST /api/v1/inference/test`

Request JSON:

```json
{"text":"source text", "source_type":"whatsapp"}
```

The response contains `summary`, backwards-compatible `items`, and typed arrays: `people`, `tasks`, `deadlines`, `decisions`, `questions`, `technical_issues`, `dependencies`, and `contradictions`.

Every typed claim contains `text`, `confidence`, `evidence`, and optional `uncertain`. Each evidence reference is backend-generated from a quote matched to the submitted source and may include `source_id`, `line_start`, `line_end`, `message_index`, and `timestamp`. Fabricated or unmatched evidence causes inference validation failure and is not returned as supported intelligence.

## `GET /api/v1/health/ollama`

Returns configured primary/fallback models, available Ollama models, and model availability flags.
