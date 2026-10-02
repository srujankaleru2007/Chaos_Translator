from fastapi import APIRouter, HTTPException

from app.inference.provider import OllamaProvider, ProviderError
from app.inference.schemas import ExtractionRequest, ExtractionResult

router = APIRouter()


@router.get("/health/ollama", tags=["health"])
async def ollama_health() -> dict:
    provider = OllamaProvider()
    try:
        status = await provider.status()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ok" if status.configured_model_available else "model_unavailable",
        "base_url": status.base_url,
        "configured_model": status.configured_model,
        "available_models": status.available_models,
        "configured_model_available": status.configured_model_available,
    }


@router.post("/inference/test", response_model=ExtractionResult, tags=["inference"])
async def inference_test(request: ExtractionRequest) -> ExtractionResult:
    provider = OllamaProvider()
    prompt = f"Source type: {request.source_type}\n\nSource content:\n{request.text}"
    try:
        result = await provider.generate_structured(
            prompt=prompt,
            schema=ExtractionResult.model_json_schema(),
            response_model=ExtractionResult,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result
