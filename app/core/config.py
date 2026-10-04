import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ai_provider: str = os.getenv("AI_PROVIDER", "ollama")
    ai_primary_model: str = os.getenv("AI_PRIMARY_MODEL", "gemma4:e4b")
    ai_fallback_model: str = os.getenv("AI_FALLBACK_MODEL", "gemma4:e2b")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    inference_retries: int = int(os.getenv("AI_RETRIES", "1"))
    inference_max_tokens: int = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "2048"))


settings = Settings()
