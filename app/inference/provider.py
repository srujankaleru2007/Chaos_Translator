import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A categorized inference provider failure."""

    def __init__(self, message: str, *, category: str = "provider_error", metadata: dict | None = None):
        super().__init__(message)
        self.category = category
        self.metadata = metadata or {}


class GroqProvider:
    """Groq adapter using the OpenAI-compatible HTTP API."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float | None = None, max_tokens: int | None = None):
        self.api_key = settings.groq_api_key if api_key is None else api_key
        self.model = model or settings.groq_model
        self.timeout = timeout or settings.groq_timeout_seconds
        self.max_tokens = max_tokens or settings.groq_max_output_tokens

    async def generate_structured(self, prompt: str, schema: dict, response_model: type[BaseModel]) -> BaseModel:
        if not self.api_key:
            raise ProviderError("Groq is not configured.", category="groq_not_configured")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Extract only information directly supported by the source. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "reasoning_effort": "low",
            "max_completion_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_result",
                    "strict": False,
                    "schema": schema,
                },
            },
        }
        request = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}", "User-Agent": "chaos-translator/0.1"},
            method="POST",
        )
        try:
            result = await asyncio.to_thread(self._request, request)
        except ProviderError:
            raise
        choice = result.get("choices", [{}])[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            logger.warning("Groq generation truncated model=%s finish_reason=length", self.model)
            raise ProviderError("Groq output reached its configured completion limit.", category="groq_truncated_output", metadata={"finish_reason": finish_reason})
        content = choice.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Groq returned no message content.", category="groq_empty_output")
        try:
            return response_model.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            category = "groq_truncated_output" if not content.rstrip().endswith(("}", "]")) else "groq_invalid_structured_output"
            metadata = self._safe_output_metadata(content, exc)
            logger.warning(
                "Groq response failed local validation model=%s category=%s content_chars=%s complete=%s top_level_keys=%s validation_fields=%s",
                self.model,
                category,
                metadata.get("content_chars"),
                metadata.get("complete"),
                metadata.get("top_level_keys"),
                metadata.get("validation_fields"),
            )
            raise ProviderError("Groq returned invalid structured output.", category=category, metadata=metadata) from exc

    def _request(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            metadata = self._safe_error_metadata(body)
            if exc.code in {401, 403}: category = "groq_authentication_error"
            elif exc.code == 429: category = "groq_rate_limit"
            elif 500 <= exc.code <= 599: category = "groq_provider_error"
            elif metadata.get("code") == "json_validate_failed": category = "groq_schema_validation"
            else: category = "groq_http_error"
            logger.warning(
                "Groq request failed model=%s status=%s category=%s code=%s type=%s finish_reason=%s usage=%s failed_generation_length=%s failed_generation_complete=%s failed_generation_json_valid=%s failed_generation_top_level_keys=%s failed_generation_counts=%s message=%s",
                self.model,
                exc.code,
                category,
                metadata.get("code"),
                metadata.get("type"),
                metadata.get("finish_reason"),
                metadata.get("usage"),
                metadata.get("failed_generation_length"),
                metadata.get("failed_generation_complete"),
                metadata.get("failed_generation_json_valid"),
                metadata.get("failed_generation_top_level_keys"),
                metadata.get("failed_generation_counts"),
                metadata.get("message"),
            )
            raise ProviderError(f"Groq request failed with HTTP {exc.code}.", category=category, metadata=metadata) from exc
        except URLError as exc:
            raise ProviderError("Groq network request failed.", category="groq_network_error") from exc
        except TimeoutError as exc:
            raise ProviderError("Groq request timed out.", category="groq_timeout") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("Groq returned invalid JSON.", category="groq_protocol_error") from exc

    @staticmethod
    def _safe_error_metadata(body: str) -> dict:
        """Keep diagnostic fields while excluding raw generations and source text."""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {"body_type": "non_json"}
        error = payload.get("error") if isinstance(payload, dict) else None
        metadata = {}
        if isinstance(error, dict):
            for field in ("code", "type"):
                if isinstance(error.get(field), str):
                    metadata[field] = error[field][:100]
            if isinstance(error.get("message"), str):
                metadata["message"] = " ".join(error["message"].split())[:300]
                retry_match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", error["message"], re.IGNORECASE)
                if retry_match:
                    metadata["retry_after_seconds"] = min(float(retry_match.group(1)), 60.0)
            failed_generation = error.get("failed_generation")
            if isinstance(failed_generation, str):
                metadata["failed_generation_length"] = len(failed_generation)
                metadata["failed_generation_complete"] = failed_generation.rstrip().endswith(("}", "]"))
                try:
                    generated_payload = json.loads(failed_generation)
                    metadata["failed_generation_json_valid"] = isinstance(generated_payload, dict)
                    metadata["failed_generation_top_level_keys"] = sorted(generated_payload) if isinstance(generated_payload, dict) else []
                    metadata["failed_generation_counts"] = {
                        key: len(value)
                        for key, value in generated_payload.items()
                        if key in {"items", "people", "tasks", "deadlines", "decisions", "questions", "technical_issues", "dependencies", "contradictions"} and isinstance(value, list)
                    } if isinstance(generated_payload, dict) else {}
                except json.JSONDecodeError:
                    metadata["failed_generation_json_valid"] = False
                    metadata["failed_generation_top_level_keys"] = []
                    metadata["failed_generation_counts"] = {}
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            if isinstance(finish_reason, str):
                metadata["finish_reason"] = finish_reason[:50]
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if isinstance(usage, dict):
            metadata["usage"] = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance(usage.get(key), int)}
        return metadata

    @staticmethod
    def _safe_output_metadata(content: str, error: ValidationError | ValueError) -> dict:
        metadata = {
            "content_chars": len(content),
            "complete": content.rstrip().endswith(("}", "]")),
        }
        try:
            payload = json.loads(content)
            metadata["top_level_keys"] = sorted(payload.keys()) if isinstance(payload, dict) else []
        except json.JSONDecodeError:
            metadata["top_level_keys"] = []
        if isinstance(error, ValidationError):
            fields = []
            for item in error.errors():
                location = item.get("loc", ())
                if location and isinstance(location[0], str):
                    fields.append(location[0])
            metadata["validation_fields"] = sorted(set(fields))
        else:
            metadata["validation_fields"] = []
        return metadata


@dataclass(frozen=True)
class OllamaStatus:
    base_url: str
    configured_model: str
    available_models: list[str]
    configured_model_available: bool


@dataclass(frozen=True)
class InferenceDiagnostics:
    active_model: str
    fallback_activated: bool
    fallback_reason: str | None
    duration_ms: float
    validation_outcome: str
    retry_count: int


class OllamaProvider:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None, max_tokens: int | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ai_primary_model
        self.timeout = timeout or settings.ollama_timeout_seconds
        self.max_tokens = max_tokens or settings.inference_max_tokens

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            category = "model_missing" if exc.code == 404 else "ollama_http_error"
            raise ProviderError(f"Ollama returned HTTP {exc.code}: {detail[:500]}", category=category) from exc
        except URLError as exc:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Start Ollama and verify the service URL."
            , category="ollama_unavailable") from exc
        except TimeoutError as exc:
            raise ProviderError(f"Ollama timed out after {self.timeout:g} seconds.", category="timeout") from exc
        except OSError as exc:
            raise ProviderError("Ollama connection failed due to a local socket error.", category="ollama_connection_error") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("Ollama returned invalid JSON.", category="ollama_protocol") from exc

    async def status(self) -> OllamaStatus:
        payload = await asyncio.to_thread(self._request, "GET", "/api/tags")
        models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
        return OllamaStatus(
            base_url=self.base_url,
            configured_model=self.model,
            available_models=models,
            configured_model_available=self.model in models,
        )

    async def generate_structured(self, prompt: str, schema: dict, response_model: type[BaseModel]) -> BaseModel:
        status = await self.status()
        if not status.configured_model_available:
            available = ", ".join(status.available_models) or "none"
            raise ProviderError(
                f"Configured Ollama model '{self.model}' is not installed. Available models: {available}."
                , category="model_missing")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract only information directly supported by the source. "
                        "Never infer a person, owner, date, status, or resolution that is not stated. "
                        "Return JSON only. Every claim must include at least one exact evidence quote "
                        "copied from the source. Use empty arrays when a category is not present."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_predict": self.max_tokens},
        }
        result = await asyncio.to_thread(self._request, "POST", "/api/chat", payload)
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama returned no message content.", category="empty_output")
        try:
            return response_model.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            category = "truncated_output" if not content.rstrip().endswith(("}", "]")) else "invalid_structured_output"
            raise ProviderError(f"Ollama local model returned invalid structured output: {exc}", category=category) from exc
