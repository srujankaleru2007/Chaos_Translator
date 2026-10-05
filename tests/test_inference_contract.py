import asyncio
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.inference.provider import ProviderError
from app.inference.schemas import EvidenceRef, ExtractionResult, PeopleExtractionResult, PersonClaim, TaskClaim
from app.main import app


class InferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.settings = __import__("app.api.routes", fromlist=["settings"]).settings

    def _settings(self, **updates):
        values = {"ai_primary_model": "qwen3.5:4b", "ai_fallback_model": "qwen3.5:4b", "groq_api_key": "test-key", "groq_api_key_secondary": ""}
        values.update(updates)
        return replace(self.settings, **values)

    def test_empty_and_whitespace_are_rejected_without_provider_call(self):
        with patch("app.api.routes.OllamaProvider") as ollama, patch("app.api.routes.GroqProvider") as groq:
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": ""}).status_code, 422)
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "   "}).status_code, 422)
            ollama.assert_not_called()
            groq.assert_not_called()

    def test_qwen_is_used_only_for_people_and_groq_handles_other_categories(self):
        calls = []

        async def local_names(self, prompt, schema, response_model):
            calls.append(("ollama", self.model, response_model.__name__, prompt))
            return PeopleExtractionResult.model_validate({
                "people": [{"name": "Asha", "text": "Asha owns the API", "confidence": 0.9, "evidence": [{"quote": "Asha owns the API"}]}]
            })

        async def groq_other_tasks(self, prompt, schema, response_model):
            calls.append(("groq", self.model, response_model.__name__, prompt))
            return ExtractionResult.model_validate({
                "summary": "A task was identified.",
                "people": [{"name": "Invented", "text": "Invented person", "confidence": 0.9, "evidence": [{"quote": "not present"}]}],
                "tasks": [{"text": "Ship the API", "confidence": 0.9, "evidence": [{"quote": "Ship the API"}]}],
            })

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local_names), \
             patch("app.api.routes.GroqProvider.generate_structured", new=groq_other_tasks):
            response = self.client.post("/api/v1/inference/test", json={"text": "Asha owns the API. Ship the API."})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([entry[0] for entry in calls], ["ollama", "groq"])
        self.assertEqual(calls[0][2], "PeopleExtractionResult")
        self.assertEqual(calls[1][2], "ExtractionResult")
        self.assertNotIn("Invented", {person["name"] for person in body["people"]})
        self.assertEqual(body["people"][0]["name"], "Asha")
        self.assertEqual(body["tasks"][0]["text"], "Ship the API")
        self.assertEqual(body["provider"], "hybrid")

    def test_cloud_consent_flag_does_not_gate_direct_groq_routing(self):
        local = AsyncMock(return_value=PeopleExtractionResult(people=[]))
        groq = AsyncMock(return_value=ExtractionResult(summary="cloud", tasks=[]))
        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local), \
             patch("app.api.routes.GroqProvider.generate_structured", new=groq):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello", "cloud_consent": False})
        self.assertEqual(response.status_code, 200)
        groq.assert_awaited_once()

    def test_groq_key_pool_round_robins_without_exposing_keys(self):
        routes = __import__("app.api.routes", fromlist=["_next_groq_api_key"])
        original_index = routes._groq_key_index
        routes._groq_key_index = 0
        try:
            with patch("app.api.routes.settings", self._settings(groq_api_key="key-a", groq_api_key_secondary="key-b")):
                self.assertEqual(routes._next_groq_api_key(), "key-a")
                self.assertEqual(routes._next_groq_api_key(), "key-b")
                self.assertEqual(routes._next_groq_api_key(), "key-a")
        finally:
            routes._groq_key_index = original_index

    def test_local_fallback_model_is_never_used_for_other_tasks(self):
        calls = []

        async def local_names(self, prompt, schema, response_model):
            calls.append(self.model)
            return PeopleExtractionResult(people=[])

        async def groq_failure(self, prompt, schema, response_model):
            raise ProviderError("unavailable", category="groq_network_error")

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local_names), \
             patch("app.api.routes.GroqProvider.generate_structured", new=groq_failure):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(calls, ["qwen3.5:4b"])
        self.assertIn("groq_network_error", response.json()["detail"]["categories"])
        self.assertNotIn("qwen3.5:4b", response.text)

    def test_missing_groq_key_is_controlled(self):
        with patch("app.api.routes.settings", self._settings(groq_api_key="")), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=AsyncMock(return_value=PeopleExtractionResult(people=[]))):
            response = self.client.post("/api/v1/inference/test", json={"text": "hello"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("groq_not_configured", response.json()["detail"]["categories"])

    def test_qwen_evidence_is_validated_and_malformed_evidence_is_partial(self):
        async def bad_names(self, prompt, schema, response_model):
            return PeopleExtractionResult.model_validate({
                "people": [{"name": "Asha", "text": "Asha", "confidence": 0.9, "evidence": [{"quote": "not in source"}]}]
            })

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=bad_names), \
             patch("app.api.routes.GroqProvider.generate_structured", new=AsyncMock(return_value=ExtractionResult(summary="ok"))):
            response = self.client.post("/api/v1/inference/test", json={"text": "source text"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])

    def test_qwen_omitted_evidence_is_rejected_by_contract_and_does_not_leak_claim(self):
        async def omitted_names(self, prompt, schema, response_model):
            claim = PersonClaim.model_construct(
                name="Asha", text="Asha", confidence=0.9, evidence=[]
            )
            return PeopleExtractionResult.model_construct(people=[claim])

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=omitted_names), \
             patch("app.api.routes.GroqProvider.generate_structured", new=AsyncMock(return_value=ExtractionResult(summary="ok"))):
            response = self.client.post("/api/v1/inference/test", json={"text": "source text"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["people"], [])

    def test_local_timeout_is_partial_and_groq_evidence_failure_is_retried_strictly(self):
        groq_calls = 0

        async def local_timeout(self, prompt, schema, response_model):
            raise asyncio.TimeoutError()

        async def groq_with_corrective_retry(self, prompt, schema, response_model):
            nonlocal groq_calls
            groq_calls += 1
            quote = "unsupported quote" if groq_calls == 1 else "Ship the API"
            return ExtractionResult(
                summary="ok",
                tasks=[TaskClaim(text="Ship the API", confidence=0.9, evidence=[EvidenceRef(quote=quote)])],
            )

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local_timeout), \
             patch("app.api.routes.GroqProvider.generate_structured", new=groq_with_corrective_retry):
            response = self.client.post("/api/v1/inference/test", json={"text": "Ship the API"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(groq_calls, 2)
        self.assertEqual(response.json()["tasks"][0]["evidence"][0]["quote"], "Ship the API")

    def test_groq_schema_validation_failure_is_retried_with_required_fields(self):
        groq_calls = 0

        async def local_names(self, prompt, schema, response_model):
            return PeopleExtractionResult(people=[])

        async def malformed_then_valid(self, prompt, schema, response_model):
            nonlocal groq_calls
            groq_calls += 1
            if groq_calls == 1:
                raise ProviderError(
                    "invalid structured output",
                    category="groq_invalid_structured_output",
                    metadata={"validation_fields": ["dependencies"]},
                )
            return ExtractionResult(summary="A supported task", tasks=[TaskClaim(text="Ship the API", confidence=0.8, evidence=[EvidenceRef(quote="Ship the API")])])

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local_names), \
             patch("app.api.routes.GroqProvider.generate_structured", new=malformed_then_valid):
            response = self.client.post("/api/v1/inference/test", json={"text": "Ship the API"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(groq_calls, 2)
        self.assertEqual(response.json()["tasks"][0]["text"], "Ship the API")

    def test_whatsapp_parser_people_survive_qwen_timeout(self):
        async def local_timeout(self, prompt, schema, response_model):
            raise asyncio.TimeoutError()

        async def groq_result(self, prompt, schema, response_model):
            return ExtractionResult(summary="task", tasks=[TaskClaim(text="Ship the API", confidence=0.8, evidence=[EvidenceRef(quote="Ship the API")])])

        with patch("app.api.routes.settings", self._settings()), \
             patch("app.api.routes.OllamaProvider.generate_structured", new=local_timeout), \
             patch("app.api.routes.GroqProvider.generate_structured", new=groq_result):
            response = self.client.post("/api/v1/inference/test", json={"source_type": "whatsapp", "text": "02/10/2026, 09:02 - Maya: Ship the API"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([person["name"] for person in response.json()["people"]], ["Maya"])
        self.assertTrue(response.json()["partial"])

    def test_length_and_shape_validation(self):
        with patch("app.api.routes.OllamaProvider.generate_structured", new=AsyncMock(return_value=PeopleExtractionResult(people=[]))), \
             patch("app.api.routes.GroqProvider.generate_structured", new=AsyncMock(return_value=ExtractionResult(summary="ok"))):
            self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "x" * 30000}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/inference/test", json={"text": "x" * 200001}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/inference/test", json={}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
