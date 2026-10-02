import asyncio
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from app.core.config import settings


class ProviderError(RuntimeError):
    """A user-actionable inference provider failure."""


@dataclass(frozen=True)
class OllamaStatus:
    base_url: str
    configured_model: str
    available_models: list[str]
    configured_model_available: bool


class OllamaProvider:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout_seconds

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
            raise ProviderError(f"Ollama returned HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Start Ollama and verify the service URL."
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(f"Ollama timed out after {self.timeout:g} seconds.") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("Ollama returned invalid JSON.") from exc

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
            )

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
            "format": schema,
            "options": {"temperature": 0},
        }
        result = await asyncio.to_thread(self._request, "POST", "/api/chat", payload)
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama returned no message content.")
        try:
            return response_model.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise ProviderError(f"Gemma returned invalid structured output: {exc}") from exc
