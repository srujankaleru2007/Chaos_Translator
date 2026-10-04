import asyncio
import json
import logging
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A categorized inference provider failure."""

    def __init__(self, message: str, *, category: str = "provider_error"):
        super().__init__(message)
        self.category = category


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
                    "content": "Extract only information directly supported by the source. Return JSON only.",
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
            raise ProviderError(f"Gemma returned invalid structured output: {exc}", category=category) from exc
