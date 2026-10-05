import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    ai_provider: str = os.getenv("AI_PROVIDER", "ollama")
    ai_primary_model: str = os.getenv("AI_PRIMARY_MODEL", "qwen3.5:4b")
    ai_fallback_model: str = os.getenv("AI_FALLBACK_MODEL", "qwen3.5:4b")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    inference_retries: int = int(os.getenv("AI_RETRIES", "1"))
    inference_max_tokens: int = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "2048"))
    people_max_output_tokens: int = int(os.getenv("AI_PEOPLE_MAX_OUTPUT_TOKENS", "768"))
    inference_chunk_max_chars: int = int(os.getenv("INFERENCE_CHUNK_MAX_CHARS", "6000"))
    local_inference_budget_seconds: float = float(os.getenv("LOCAL_INFERENCE_BUDGET_SECONDS", "45"))
    mongo_enabled: bool = os.getenv("MONGO_ENABLED", "false").lower() == "true"
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    mongo_database: str = os.getenv("MONGO_DATABASE", "chaos_translator")
    mongo_server_selection_timeout_ms: int = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "2000"))
    cloud_fallback_enabled: bool = os.getenv("CLOUD_FALLBACK_ENABLED", "false").lower() == "true"
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_api_key_secondary: str = os.getenv("GROQ_API_KEY_SECONDARY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    groq_timeout_seconds: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
    groq_max_output_tokens: int = int(os.getenv("GROQ_MAX_OUTPUT_TOKENS", "4096"))


settings = Settings()
