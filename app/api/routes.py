import logging
import time

from fastapi import APIRouter, HTTPException

from app.inference.provider import OllamaProvider, ProviderError
from app.core.config import settings
from app.inference.schemas import ExtractionRequest, ExtractionResult

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_evidence(result: ExtractionResult, source: str) -> ExtractionResult:
    """Reject model claims whose evidence is not present in the submitted source."""
    source_normalized = " ".join(source.split()).casefold()
    for category in (
        "people", "tasks", "deadlines", "decisions", "questions",
        "technical_issues", "dependencies", "contradictions",
    ):
        for claim in getattr(result, category):
            valid = [evidence for evidence in claim.evidence
                     if " ".join(evidence.quote.split()).casefold() in source_normalized]
            if not valid:
                raise ProviderError(
                    f"Model returned unsupported evidence for {category}.",
                    category="unsupported_evidence",
                )
            claim.evidence = valid
    return result


@router.get("/health/ollama", tags=["health"])
async def ollama_health() -> dict:
    try:
        primary = await OllamaProvider(model=settings.ai_primary_model).status()
        fallback = await OllamaProvider(model=settings.ai_fallback_model).status()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ok" if primary.configured_model_available and fallback.configured_model_available else "model_unavailable",
        "base_url": primary.base_url,
        "configured_model": primary.configured_model,
        "primary_model": settings.ai_primary_model,
        "fallback_model": settings.ai_fallback_model,
        "available_models": primary.available_models,
        "primary_model_available": primary.configured_model_available,
        "fallback_model_available": fallback.configured_model_available,
        "configured_model_available": primary.configured_model_available,
    }


@router.post("/inference/test", response_model=ExtractionResult, tags=["inference"])
async def inference_test(request: ExtractionRequest) -> ExtractionResult:
    started = time.perf_counter()
    prompt = f"""Source type: {request.source_type}

Extract a comprehensive but strictly source-grounded intelligence record.
Populate these categories when supported: people, tasks, deadlines, decisions,
questions, technical_issues, dependencies, and contradictions. For each claim,
copy an exact quote from the source into evidence[].quote. Do not turn guesses,
unstated ownership, or implied dates into facts. A question is unanswered unless
the source explicitly answers it. A contradiction requires two source-supported
claims that conflict; leave resolution null when the source does not resolve it.
Keep the legacy items array populated for the most important claims.

Source content:
{request.text}"""
    errors = []
    for model in dict.fromkeys((settings.ai_primary_model, settings.ai_fallback_model)):
        for attempt in range(settings.inference_retries + 1):
            try:
                result = await OllamaProvider(model=model).generate_structured(
                    prompt=prompt, schema=ExtractionResult.model_json_schema(), response_model=ExtractionResult
                )
                result = _validate_evidence(result, request.text)
                logger.info("inference model=%s fallback=%s duration_ms=%.1f validation=passed", model, model != settings.ai_primary_model, (time.perf_counter() - started) * 1000)
                return result
            except ProviderError as exc:
                errors.append({"model": model, "attempt": attempt + 1, "category": exc.category})
                logger.warning("inference model=%s attempt=%d category=%s", model, attempt + 1, exc.category)
                if attempt < settings.inference_retries:
                    continue
                break
    logger.error("inference failed models=%s duration_ms=%.1f", [item["model"] for item in errors], (time.perf_counter() - started) * 1000)
    raise HTTPException(
        status_code=503,
        detail={
            "error": "all_inference_models_failed",
            "message": "All configured inference models failed. Check Ollama availability and model configuration.",
            "attempts": errors,
        },
    )
