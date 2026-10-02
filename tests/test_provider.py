import asyncio
import unittest

from pydantic import BaseModel

from app.inference.provider import OllamaProvider, ProviderError


class Result(BaseModel):
    value: str


class ProviderTests(unittest.TestCase):
    def test_invalid_model_error_is_actionable(self):
        provider = OllamaProvider(base_url="http://127.0.0.1:1", model="missing:model", timeout=0.1)
        with self.assertRaises(ProviderError) as context:
            asyncio.run(provider.generate_structured("hello", Result.model_json_schema(), Result))
        self.assertIn("Cannot connect to Ollama", str(context.exception))

    def test_provider_is_configurable(self):
        provider = OllamaProvider(base_url="http://example.test", model="gemma4:e2b", timeout=5)
        self.assertEqual(provider.model, "gemma4:e2b")
        self.assertEqual(provider.base_url, "http://example.test")


if __name__ == "__main__":
    unittest.main()
