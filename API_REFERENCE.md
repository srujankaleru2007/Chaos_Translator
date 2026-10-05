# API reference

## `POST /api/v1/inference/test`

Request JSON:

```json
{"text":"source text", "source_type":"whatsapp", "cloud_consent":false}
```

The request accepts up to 200,000 characters. WhatsApp inputs are split at message boundaries and aggregated; responses expose `partial`, `chunks_processed`, `chunks_total`, and `failed_chunks`. The response contains `summary`, backwards-compatible `items`, and typed arrays: `people`, `tasks`, `deadlines`, `decisions`, `questions`, `technical_issues`, `dependencies`, and `contradictions`.

Every typed claim contains `text`, `confidence`, `evidence`, and optional `uncertain`. Each evidence reference is backend-generated from a quote matched to the submitted source and may include `source_id`, `line_start`, `line_end`, `message_index`, and `timestamp`. Fabricated or unmatched evidence causes inference validation failure and is not returned as supported intelligence.

## `GET /api/v1/health/ollama`

Returns configured primary/fallback models, available Ollama models, and model availability flags.

## Cloud fallback request

`cloud_consent` is optional and defaults to `false`. Set it to `true` only when the user has agreed that the source may be sent to Groq. The backend must also have `CLOUD_FALLBACK_ENABLED=true` and `GROQ_API_KEY` configured. Successful responses include `provider`, `model`, `cloud_fallback_used`, and `correlation_id`.
