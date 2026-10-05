import asyncio
from difflib import SequenceMatcher
import logging
import re
import time
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.inference.chunking import split_source
from app.inference.provider import GroqProvider, OllamaProvider, ProviderError
from app.inference.schemas import EvidenceRef, ExtractionRequest, ExtractionResult, PeopleExtractionResult, PersonClaim
from app.ingestion.schemas import WhatsAppIngestionRequest
from app.ingestion.documents import MAX_DOCUMENT_SIZE_BYTES, DoclingUnavailable, DocumentIngestionError, convert_document_bytes
from app.ingestion.images import MAX_IMAGE_SIZE_BYTES, ImageIngestionError, convert_image_bytes
from app.ingestion.audio import MAX_AUDIO_SIZE_BYTES, AudioIngestionError, AudioRuntimeUnavailable, transcribe_audio_bytes
from app.ingestion.whatsapp import parse_whatsapp_text
from app.source.models import CanonicalSource

router = APIRouter()
logger = logging.getLogger(__name__)
GROQ_REQUEST_LOCK = asyncio.Lock()
_groq_key_index = 0


def _next_groq_api_key() -> str:
    global _groq_key_index
    keys = [key for key in (settings.groq_api_key, settings.groq_api_key_secondary) if key]
    if not keys:
        return ""
    key = keys[_groq_key_index % len(keys)]
    _groq_key_index += 1
    return key
WHATSAPP_MESSAGE = re.compile(r"^(?P<timestamp>\d{1,2}[/:.-]\d{1,2}[/:.-]\d{2,4}[^-]*?)\s+-\s+(?P<author>[^:]+):\s+(?P<body>.*)$")


def _evidence_locator(quote: str, source: str):
    normalized_quote = " ".join(quote.split()).casefold()
    if not normalized_quote:
        return None
    lines = source.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if normalized_quote in " ".join(line.split()).casefold():
            match = WHATSAPP_MESSAGE.match(line.strip())
            return {"quote": line.strip() if quote.strip() == line.strip() else quote.strip(), "source_id": "source-1", "line_start": line_number, "line_end": line_number, "message_index": sum(1 for prior in lines[:line_number] if WHATSAPP_MESSAGE.match(prior.strip())) or None, "timestamp": match.group("timestamp").strip() if match else None, "page_number": None}
    return None


def _parsed_whatsapp_people(source_type: str, source: str) -> list[PersonClaim]:
    """Recover parser-proven participants when the local model omits them."""
    if source_type.casefold() != "whatsapp":
        return []
    parsed = parse_whatsapp_text(source)
    people: dict[str, PersonClaim] = {}
    for unit in parsed.units:
        name = (unit.sender_or_speaker or "").strip()
        if not name or name.casefold() in people:
            continue
        quote = next((line.strip() for line in source.splitlines() if f" - {name}:" in line), unit.text.strip())
        people[name.casefold()] = PersonClaim(
            name=name,
            text=f"{name} appears as a participant in the conversation.",
            confidence=1.0,
            evidence=[EvidenceRef(quote=quote)],
        )
    return list(people.values())


def _merge_people(model_people: list[PersonClaim], parsed_people: list[PersonClaim]) -> list[PersonClaim]:
    merged: dict[str, PersonClaim] = {person.name.casefold(): person for person in model_people}
    for person in parsed_people:
        merged.setdefault(person.name.casefold(), person)
    return list(merged.values())


def _claim_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.casefold()).split())


def _merge_claim(claims: list, candidate) -> bool:
    candidate_key = _claim_key(candidate.text)
    for existing in claims:
        existing_key = _claim_key(existing.text)
        if existing_key == candidate_key or SequenceMatcher(None, existing_key, candidate_key).ratio() >= 0.92:
            known = {" ".join(evidence.quote.split()).casefold() for evidence in existing.evidence}
            existing.evidence.extend(evidence for evidence in candidate.evidence if " ".join(evidence.quote.split()).casefold() not in known)
            existing.confidence = max(existing.confidence, candidate.confidence)
            return True
    return False


def _validate_evidence(result, source: str, categories: tuple[str, ...] | None = None):
    source_normalized = " ".join(source.split()).casefold()
    categories = categories or ("people", "tasks", "deadlines", "decisions", "questions", "technical_issues", "dependencies", "contradictions")
    for category in categories:
        for claim_index, claim in enumerate(getattr(result, category)):
            valid = []
            for evidence in claim.evidence:
                locator = _evidence_locator(evidence.quote, source)
                if locator:
                    valid.append(type(evidence).model_validate(locator))
            if not valid:
                raise ProviderError(
                    f"Model returned unsupported evidence for {category}.",
                    category="evidence_validation",
                    metadata={"claim_category": category, "claim_index": claim_index, "evidence_count": len(claim.evidence)},
                )
            claim.evidence = valid
    for item in getattr(result, "items", []):
        if " ".join(item.evidence_quote.split()).casefold() not in source_normalized:
            raise ProviderError(
                "Model returned unsupported legacy evidence.",
                category="evidence_validation",
                metadata={"claim_category": "items"},
            )
    return result


def _prompt(source_type: str, text: str) -> str:
    return f"""Source type: {source_type}

Extract a comprehensive but strictly source-grounded intelligence record.
Populate people, tasks, deadlines, decisions, questions, technical_issues,
dependencies, and contradictions when supported. Every claim needs an exact
evidence quote copied from the source. Never invent ownership, dates, statuses,
resolutions, IDs, timestamps, or page numbers. Use empty arrays when absent.

Source content:
{text}"""


def _people_prompt(source_type: str, text: str) -> str:
    return f"""Source type: {source_type}

Extract only people and names explicitly present in the source.
Return an empty people array when no person is directly supported.
Never infer, normalize into, or invent a person, role, ownership, or identity.
Every person claim must include an exact evidence quote copied from the source.

Source content:
{text}"""


def _groq_prompt(source_type: str, text: str) -> str:
    return f"""Source type: {source_type}

Extract tasks, deadlines, decisions, questions, technical issues,
dependencies, and contradictions that are directly supported by the source.
People and names are extracted separately by the local model: return an empty
people array and do not add person claims here. Every claim needs an exact
evidence quote copied from the source. Never invent ownership, dates, statuses,
resolutions, IDs, timestamps, or page numbers. Always include a concise
summary string. Return `items` as an empty array; do not duplicate typed
category claims in the legacy highlights field. Use empty arrays when absent.
Return no more than 20 claims per category and keep only the strongest
source-supported claims. Set confidence using this evidence rubric: 0.95 for
an explicit direct statement, 0.80 for a clear source-grounded paraphrase, and
0.60 for a supported but uncertain implication. Do not use the same confidence
for unrelated claims unless their evidence strength is genuinely equal. When
deadlines conflict, preserve both original claims and evidence, label an
official deadline or internal target only when the source explicitly does so,
and never resolve the conflict without source support. Each decision must include `decision`; each
dependency must include `depends_on`; each contradiction must include both
`claim_a` and `claim_b`. Every claim object must include `text`, a numeric
`confidence`, and an `evidence` array containing objects with a `quote`.
Use exactly these top-level JSON keys: `summary`, `items`, `people`, `tasks`,
`deadlines`, `decisions`, `questions`, `technical_issues`, `dependencies`,
and `contradictions`. Do not use alternate keys such as `description`,
`dependency`, or `contradiction`.
Canonical examples: a task is `{{"text":"...","confidence":0.8,"evidence":[{{"quote":"..."}}]}}`;
a decision object has exactly `text`, `confidence`, `evidence`, and `decision`;
a dependency object has exactly `text`, `confidence`, `evidence`, and
`depends_on`; a contradiction object has exactly `text`, `confidence`,
`evidence`, `claim_a`, and `claim_b`.

Source content:
{text}"""


async def _infer_one(source_text: str, validation_source: str, request: ExtractionRequest, correlation_id: str, local_deadline: float, errors: list[dict]) -> ExtractionResult | None:
    people: list[PersonClaim] = _parsed_whatsapp_people(request.source_type, validation_source)
    local_people_failed = False
    remaining = local_deadline - time.perf_counter()
    if remaining <= 0:
        local_people_failed = True
        errors.append({"provider": "ollama", "model": settings.ai_primary_model, "attempt": 1, "category": "local_budget_exhausted"})
    else:
        try:
            local_result = await asyncio.wait_for(
                OllamaProvider(
                    model=settings.ai_primary_model,
                    timeout=min(settings.ollama_timeout_seconds, remaining),
                    max_tokens=settings.people_max_output_tokens,
                ).generate_structured(
                    prompt=_people_prompt(request.source_type, source_text),
                    schema=PeopleExtractionResult.model_json_schema(),
                    response_model=PeopleExtractionResult,
                ),
                timeout=remaining,
            )
            people = _merge_people(_validate_evidence(local_result, validation_source, ("people",)).people, people)
        except asyncio.TimeoutError:
            local_people_failed = True
            logger.warning("inference correlation_id=%s provider=ollama model=%s category=local_timeout", correlation_id, settings.ai_primary_model)
            errors.append({"provider": "ollama", "model": settings.ai_primary_model, "attempt": 1, "category": "local_timeout"})
        except ProviderError as exc:
            local_people_failed = True
            logger.warning("inference correlation_id=%s provider=ollama model=%s category=%s metadata=%s", correlation_id, settings.ai_primary_model, exc.category, exc.metadata)
            errors.append({"provider": "ollama", "model": settings.ai_primary_model, "attempt": 1, "category": exc.category})

    groq_prompt = _groq_prompt(request.source_type, source_text)
    for attempt in range(1, 3):
        try:
            async with GROQ_REQUEST_LOCK:
                groq_provider = GroqProvider(
                    api_key=_next_groq_api_key(),
                    model=settings.groq_model,
                    timeout=settings.groq_timeout_seconds,
                    max_tokens=settings.groq_max_output_tokens,
                )
                groq_result = await asyncio.wait_for(
                    groq_provider.generate_structured(
                        prompt=groq_prompt,
                        schema=ExtractionResult.model_json_schema(),
                        response_model=ExtractionResult,
                    ),
                    timeout=settings.groq_timeout_seconds,
                )
            # Groq owns every category except people. Drop any accidental person
            # claims before evidence validation so names can only come from Qwen.
            groq_result = groq_result.model_copy(update={"people": []})
            groq_result = _validate_evidence(groq_result, validation_source)
            return groq_result.model_copy(
                update={
                    "people": people,
                    "provider": "hybrid" if people else "groq",
                    "model": f"{settings.ai_primary_model}+{settings.groq_model}" if people else settings.groq_model,
                    "cloud_fallback_used": False,
                    "correlation_id": correlation_id,
                    "partial": local_people_failed,
                }
            )
        except asyncio.TimeoutError:
            errors.append({"provider": "groq", "model": settings.groq_model, "attempt": attempt, "category": "groq_timeout"})
            break
        except ProviderError as exc:
            logger.warning("inference correlation_id=%s provider=groq model=%s attempt=%s category=%s metadata=%s", correlation_id, settings.groq_model, attempt, exc.category, exc.metadata)
            error = {"provider": "groq", "model": settings.groq_model, "attempt": attempt, "category": exc.category}
            if isinstance(exc.metadata.get("retry_after_seconds"), (int, float)):
                error["retry_after_seconds"] = exc.metadata["retry_after_seconds"]
            errors.append(error)
            if exc.category == "groq_rate_limit" and attempt == 1:
                retry_after = exc.metadata.get("retry_after_seconds", 0)
                if isinstance(retry_after, (int, float)) and 0 < retry_after <= 60:
                    await asyncio.sleep(retry_after)
                    continue
            if exc.category not in {"evidence_validation", "groq_invalid_structured_output"} or attempt == 2:
                break
            if exc.category == "evidence_validation":
                correction = (
                    "\nCORRECTION: Your previous evidence was not found in the source. "
                    "Return only claims whose evidence.quote is an exact contiguous quote "
                    "from the source, including original wording. Remove any claim you "
                    "cannot support exactly."
                )
            else:
                fields = ", ".join(str(field) for field in exc.metadata.get("validation_fields", [])) or "the required fields"
                correction = (
                    f"\nCORRECTION: The previous JSON omitted or invalidated {fields}. "
                    "Return only the canonical schema. Every dependency must include a "
                    "non-empty depends_on string; every decision must include decision; "
                    "every contradiction must include claim_a and claim_b; every claim "
                    "must include text, numeric confidence, and non-empty evidence."
                )
            groq_prompt = _groq_prompt(request.source_type, source_text) + correction
    return None


def _merge_results(results: list[ExtractionResult], total: int, failed: list[int], correlation_id: str) -> ExtractionResult:
    categories = ("people", "tasks", "deadlines", "decisions", "questions", "technical_issues", "dependencies", "contradictions")
    values = {category: [] for category in categories}; items = []; seen = set()
    for result in results:
        for item in result.items:
            key = ("item", item.kind, item.text.casefold())
            if key not in seen: seen.add(key); items.append(item)
        for category in categories:
            for claim in getattr(result, category):
                if not _merge_claim(values[category], claim):
                    values[category].append(claim)
    return ExtractionResult(summary=" ".join(result.summary for result in results if result.summary), items=items, **values, provider="mixed" if len({result.provider for result in results}) > 1 else results[0].provider, model="mixed" if len({result.model for result in results}) > 1 else results[0].model, cloud_fallback_used=any(result.cloud_fallback_used for result in results), correlation_id=correlation_id, partial=bool(failed) or any(result.partial for result in results), chunks_processed=len(results), chunks_total=total, failed_chunks=failed)


@router.get("/health/ollama", tags=["health"])
async def ollama_health() -> dict:
    try:
        primary = await OllamaProvider(model=settings.ai_primary_model).status(); fallback = await OllamaProvider(model=settings.ai_fallback_model).status()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok" if primary.configured_model_available and fallback.configured_model_available else "model_unavailable", "base_url": primary.base_url, "configured_model": primary.configured_model, "primary_model": settings.ai_primary_model, "fallback_model": settings.ai_fallback_model, "available_models": primary.available_models, "primary_model_available": primary.configured_model_available, "fallback_model_available": fallback.configured_model_available, "configured_model_available": primary.configured_model_available}


@router.post("/sources/whatsapp", response_model=CanonicalSource, tags=["sources"])
async def ingest_whatsapp(request: WhatsAppIngestionRequest) -> CanonicalSource:
    return parse_whatsapp_text(request.text, filename=request.filename, file_size_bytes=request.file_size_bytes)


@router.post("/sources/document", response_model=CanonicalSource, tags=["sources"])
async def ingest_document(file: UploadFile = File(...)) -> CanonicalSource:
    filename = file.filename or "document"
    try:
        chunks: list[bytes] = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_DOCUMENT_SIZE_BYTES:
                raise DocumentIngestionError(f"Documents must be {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
            chunks.append(chunk)
        data = b"".join(chunks)
        return await asyncio.to_thread(convert_document_bytes, data, filename=filename, declared_mime_type=file.content_type)
    except DoclingUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocumentIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sources/image", response_model=CanonicalSource, tags=["sources"])
async def ingest_image(file: UploadFile = File(...)) -> CanonicalSource:
    filename = file.filename or "image"
    try:
        chunks: list[bytes] = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_IMAGE_SIZE_BYTES:
                raise ImageIngestionError(f"Images must be {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
            chunks.append(chunk)
        return await asyncio.to_thread(convert_image_bytes, b"".join(chunks), filename=filename, declared_mime_type=file.content_type)
    except ImageIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sources/audio", response_model=CanonicalSource, tags=["sources"])
async def ingest_audio(file: UploadFile = File(...)) -> CanonicalSource:
    filename = file.filename or "audio"
    try:
        chunks: list[bytes] = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_AUDIO_SIZE_BYTES:
                raise AudioIngestionError(f"Audio files must be {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
            chunks.append(chunk)
        return await asyncio.to_thread(transcribe_audio_bytes, b"".join(chunks), filename=filename, declared_mime_type=file.content_type)
    except AudioRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AudioIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/inference/test", response_model=ExtractionResult, tags=["inference"])
async def inference_test(request: ExtractionRequest) -> ExtractionResult:
    started = time.perf_counter(); correlation_id = uuid4().hex[:12]; chunks = split_source(request.text, max_chars=settings.inference_chunk_max_chars); errors: list[dict] = []; results: list[ExtractionResult] = []; failed: list[int] = []; local_deadline = started + settings.local_inference_budget_seconds
    for index, chunk in enumerate(chunks, start=1):
        result = await _infer_one(chunk, request.text, request, correlation_id, local_deadline, errors)
        (failed if result is None else results).append(index if result is None else result)
    if results:
        return _merge_results(results, len(chunks), failed, correlation_id)
    categories = sorted({item["category"] for item in errors})
    logger.error("inference correlation_id=%s failed categories=%s duration_ms=%.1f", correlation_id, categories, (time.perf_counter() - started) * 1000)
    if "groq_rate_limit" in categories:
        message = "Groq cloud inference is temporarily rate-limited. Wait briefly and retry."
    else:
        message = "Inference failed for all configured providers. Check failure categories and server logs using the correlation ID."
    raise HTTPException(status_code=503, detail={"error": "all_inference_models_failed", "message": message, "correlation_id": correlation_id, "categories": categories, "attempts": errors})
