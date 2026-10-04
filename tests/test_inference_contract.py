import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.inference.provider import ProviderError
from app.inference.schemas import ExtractionResult
from app.main import app


class InferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_empty_and_whitespace_are_rejected_without_provider_call(self):
        with patch("app.api.routes.OllamaProvider") as provider:
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "", "source_type": "text"}).status_code, 422)
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "   ", "source_type": "text"}).status_code, 422)
            provider.assert_not_called()

    def test_length_and_shape_validation(self):
        with patch("app.api.routes.OllamaProvider.generate_structured", new=AsyncMock(return_value=ExtractionResult(summary="ok", items=[]))):
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "x" * 30000}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "x" * 30001}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/inference/test", json={}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": 4}).status_code, 422)

    def test_primary_success_uses_validated_result(self):
        result = ExtractionResult(summary="ok", items=[])
        with patch("app.api.routes.OllamaProvider.generate_structured", new=AsyncMock(return_value=result)):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello", "source_type": "text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result.model_dump())

    def test_primary_failure_falls_back(self):
        calls = []
        async def generate(self, prompt, schema, response_model):
            calls.append(self.model)
            if self.model == "gemma4:e4b": raise ProviderError("down", category="ollama_unavailable")
            return response_model(summary="fallback", items=[])
        with patch("app.api.routes.OllamaProvider.generate_structured", new=generate):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello", "source_type": "text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"], "fallback")
        self.assertIn("gemma4:e2b", calls)

    def test_both_fail_return_safe_structured_503(self):
        async def fail(self, prompt, schema, response_model):
            raise ProviderError("secret upstream detail", category="timeout")
        with patch("app.api.routes.OllamaProvider.generate_structured", new=fail):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello", "source_type": "text"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["error"], "all_inference_models_failed")
        self.assertNotIn("secret upstream detail", response.text)


if __name__ == "__main__":
    unittest.main()
