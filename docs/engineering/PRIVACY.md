# Privacy and cloud fallback

Ollama remains local for people/name extraction. Source content is sent to the configured Groq API for all other intelligence categories. The Groq API key is read only by the backend environment and is never returned to the frontend or written to project files.

The frontend starts extraction directly; it does not receive or transmit the API key. The legacy `cloud_consent` field is accepted for request compatibility, but configured server-side Groq routing is not gated by a browser checkbox. Correlation IDs and provider metadata are logged; raw source text, prompts, and credentials are not logged.
