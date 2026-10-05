import asyncio
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request
import unittest
from unittest.mock import patch

from pydantic import BaseModel

from app.inference.provider import GroqProvider, OllamaProvider, ProviderError


class Result(BaseModel):
    value: str


class ProviderTests(unittest.TestCase):
    def test_invalid_model_error_is_actionable(self):
        provider = OllamaProvider(base_url="http://127.0.0.1:1", model="missing:model", timeout=0.1)
        with self.assertRaises(ProviderError) as context:
            asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertIn("Cannot connect to Ollama", str(context.exception))

    def test_provider_is_configurable(self):
        provider = OllamaProvider(base_url="http://example.test", model="qwen3.5:4b", timeout=5)
        self.assertEqual(provider.model, "qwen3.5:4b")
        self.assertEqual(provider.base_url, "http://example.test")

    def test_groq_missing_key_is_safe_configuration_error(self):
        provider = GroqProvider(api_key="", timeout=1)
        with self.assertRaises(ProviderError) as context:
            asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_not_configured")

    def test_groq_rate_limit_is_categorized(self):
        provider = GroqProvider(api_key="test", timeout=1)
        with patch.object(provider, "_request", side_effect=ProviderError("rate", category="groq_rate_limit")):
            with self.assertRaises(ProviderError) as context:
                asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_rate_limit")

    def test_groq_json_validate_error_preserves_safe_metadata(self):
        body = b'{"error":{"message":"Failed to validate JSON. See failed_generation.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":"{\\"items\\":[1]}"}}'
        error = HTTPError("https://api.groq.com", 400, "Bad Request", {}, BytesIO(body))
        provider = GroqProvider(api_key="test", timeout=1)
        with patch("app.inference.provider.urlopen", side_effect=error):
            with self.assertRaises(ProviderError) as context:
                asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_schema_validation")
        self.assertEqual(context.exception.metadata["code"], "json_validate_failed")
        self.assertNotIn("items", str(context.exception))

    def test_groq_finish_reason_length_is_truncation(self):
        provider = GroqProvider(api_key="test", timeout=1)
        with patch.object(provider, "_request", return_value={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}):
            with self.assertRaises(ProviderError) as context:
                asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_truncated_output")

    def test_groq_local_validation_reports_missing_fields_without_source(self):
        provider = GroqProvider(api_key="test", timeout=1)
        with patch.object(provider, "_request", return_value={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}):
            with self.assertRaises(ProviderError) as context:
                asyncio.run(provider.generate_structured("private source", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_invalid_structured_output")
        self.assertEqual(context.exception.metadata["validation_fields"], ["value"])
        self.assertNotIn("private source", str(context.exception))

    def test_groq_uses_current_completion_field_and_best_effort_schema(self):
        captured = {}
        provider = GroqProvider(api_key="test", timeout=1, max_tokens=8192)

        def fake_request(request):
            captured.update(__import__("json").loads(request.data.decode("utf-8")))
            return {"choices": [{"finish_reason": "stop", "message": {"content": '{"value":"ok"}'}}]}

        with patch.object(provider, "_request", side_effect=fake_request):
            result = asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))

        self.assertEqual(result.value, "ok")
        self.assertEqual(captured["max_completion_tokens"], 8192)
        self.assertNotIn("max_tokens", captured)
        self.assertEqual(captured["reasoning_effort"], "low")
        self.assertFalse(captured["response_format"]["json_schema"]["strict"])

    def test_groq_rate_limit_metadata_extracts_bounded_retry_delay(self):
        body = b'{"error":{"message":"Rate limit reached. Please try again in 34.44s.","type":"tokens","code":"rate_limit_exceeded"}}'
        error = HTTPError("https://api.groq.com", 429, "Too Many Requests", {}, BytesIO(body))
        provider = GroqProvider(api_key="test", timeout=1)
        with patch("app.inference.provider.urlopen", side_effect=error):
            with self.assertRaises(ProviderError) as context:
                asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertEqual(context.exception.category, "groq_rate_limit")
        self.assertEqual(context.exception.metadata["retry_after_seconds"], 34.44)


if __name__ == "__main__":
    unittest.main()
