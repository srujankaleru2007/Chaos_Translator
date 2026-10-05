"""Docling-first image and screenshot OCR ingestion."""

from datetime import datetime, timezone
from io import BytesIO
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from PIL import Image

from app.source.models import CanonicalSource, ContentType, ContentUnit, ExtractionMetadata, ProcessingStatus, SourceLocator, SourceType

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
OCR_TIMEOUT_SECONDS = 30.0


class ImageIngestionError(RuntimeError):
    """An image cannot be safely or reliably ingested."""


class OcrUnavailable(ImageIngestionError):
    """The optional OCR fallback is not available."""


def _source_id(data: bytes, filename: str) -> str:
    return f"image-{hashlib.sha256(filename.encode('utf-8') + b'\0' + data).hexdigest()[:24]}"


def validate_image_payload(data: bytes, *, filename: str, declared_mime_type: str | None = None) -> None:
    suffix = Path(filename).suffix.casefold()
    expected_mime = MIME_TYPES.get(suffix)
    if expected_mime is None:
        raise ImageIngestionError("Only PNG, JPEG, WEBP, BMP, and TIFF images are supported in Phase 4.")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise ImageIngestionError(f"Images must be {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
    if not data:
        raise ImageIngestionError("The image is empty.")
    normalized_mime = (declared_mime_type or "").split(";", 1)[0].strip().casefold()
    if normalized_mime and normalized_mime != "application/octet-stream" and normalized_mime != expected_mime:
        raise ImageIngestionError(f"The declared MIME type does not match {suffix}.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except Exception as exc:
        raise ImageIngestionError("The image signature or structure is invalid.") from exc


def _failed_source(filename: str, data: bytes, message: str, warnings: list[str] | None = None) -> CanonicalSource:
    status = ProcessingStatus.FAILED
    all_warnings = warnings or []
    return CanonicalSource(
        source_id=_source_id(data, filename),
        source_type=SourceType.IMAGE,
        original_filename=filename,
        mime_type=MIME_TYPES.get(Path(filename).suffix.casefold()),
        file_size_bytes=len(data),
        processing_status=status,
        warnings=all_warnings,
        errors=[message],
        extraction=ExtractionMetadata(method="image_ocr", tool="docling+pytesseract", status=status, warnings=all_warnings, errors=[message], extracted_at=datetime.now(timezone.utc)),
    )


def _docling_units(document: Any, source_id: str) -> list[ContentUnit]:
    iterator = getattr(document, "iterate_items", None)
    if not callable(iterator):
        return []
    units: list[ContentUnit] = []
    for position, pair in enumerate(iterator()):
        item, level = pair
        text = getattr(item, "text", None)
        if not isinstance(text, str) or not text.strip():
            exporter = getattr(item, "export_to_markdown", None)
            text = exporter() if callable(exporter) else ""
        if not isinstance(text, str) or not text.strip():
            continue
        provenance = getattr(item, "prov", None) or []
        first = provenance[0] if provenance else None
        bbox = getattr(first, "bbox", None) if first else None
        bbox_data = bbox.model_dump(mode="json") if hasattr(bbox, "model_dump") else str(bbox) if bbox is not None else None
        metadata: dict[str, Any] = {"docling_level": level, "ocr_engine": "docling"}
        if bbox_data is not None:
            metadata["bbox"] = bbox_data
        locator = SourceLocator(source_id=source_id, block_index=position, metadata=metadata)
        units.append(ContentUnit(source_id=source_id, content_type=ContentType.OCR_BLOCK, text=text.strip(), position=len(units), locator=locator, metadata=metadata))
    return units


def _pytesseract_runner(data: bytes, timeout_seconds: float) -> list[dict[str, Any]]:
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise OcrUnavailable("PyTesseract is not installed for the OCR fallback.") from exc
    with Image.open(BytesIO(data)) as image:
        try:
            result = pytesseract.image_to_data(image, output_type=Output.DICT, timeout=timeout_seconds)
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractException) as exc:
            raise OcrUnavailable("The Tesseract executable is not available for the OCR fallback.") from exc
    blocks: list[dict[str, Any]] = []
    for index, text in enumerate(result.get("text", [])):
        normalized = str(text).strip()
        if not normalized:
            continue
        blocks.append({"text": normalized, "bbox": {key: int(result[key][index]) for key in ("left", "top", "width", "height")}, "confidence": result.get("conf", [None])[index]})
    return blocks


def convert_image_bytes(data: bytes, *, filename: str, declared_mime_type: str | None = None, converter: Any | None = None, ocr_runner: Callable[[bytes, float], list[dict[str, Any]]] | None = None, ocr_timeout_seconds: float = OCR_TIMEOUT_SECONDS) -> CanonicalSource:
    suffix = Path(filename).suffix.casefold()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ImageIngestionError("Only PNG, JPEG, WEBP, BMP, and TIFF images are supported in Phase 4.")
    validate_image_payload(data, filename=filename, declared_mime_type=declared_mime_type)
    source_id = _source_id(data, filename)
    warnings: list[str] = []
    if converter is None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            warnings.append("Docling is not installed; the controlled OCR fallback was attempted.")
        else:
            converter = DocumentConverter()
    if converter is not None:
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary_path = temporary.name
                temporary.write(data)
                temporary.flush()
            result = converter.convert(temporary_path)
            document = getattr(result, "document", None)
            units = _docling_units(document, source_id) if document is not None else []
            if units:
                extraction = ExtractionMetadata(method="image_ocr", tool="docling", status=ProcessingStatus.COMPLETED, warnings=warnings, extracted_at=datetime.now(timezone.utc))
                return CanonicalSource(source_id=source_id, source_type=SourceType.IMAGE, original_filename=filename, mime_type=MIME_TYPES[suffix], file_size_bytes=len(data), processing_status=ProcessingStatus.COMPLETED, warnings=warnings, units=units, extraction=extraction, original_metadata={"format": suffix.lstrip("."), "ocr_engine": "docling"})
            warnings.append("Docling returned no OCR text; the controlled OCR fallback was attempted.")
        except Exception as exc:
            warnings.append(f"Docling OCR failed with {type(exc).__name__}; the controlled OCR fallback was attempted.")
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
    runner = ocr_runner or _pytesseract_runner
    try:
        blocks = runner(data, ocr_timeout_seconds)
    except OcrUnavailable as exc:
        return _failed_source(filename, data, str(exc), warnings)
    except TimeoutError:
        return _failed_source(filename, data, "OCR exceeded its time limit.", warnings)
    except Exception as exc:
        return _failed_source(filename, data, f"OCR failed with {type(exc).__name__}.", warnings)
    if not blocks:
        return _failed_source(filename, data, "OCR produced no text.", warnings)
    units = []
    for position, block in enumerate(blocks):
        metadata = {"ocr_engine": "pytesseract", "confidence": block.get("confidence")}
        if block.get("bbox") is not None:
            metadata["bbox"] = block["bbox"]
        units.append(ContentUnit(source_id=source_id, content_type=ContentType.OCR_BLOCK, text=block["text"], position=position, locator=SourceLocator(source_id=source_id, block_index=position, metadata=metadata), metadata=metadata))
    warnings.append("Pytesseract fallback was used; verify OCR text and coordinates against the source image.")
    extraction = ExtractionMetadata(method="image_ocr", tool="pytesseract", status=ProcessingStatus.PARTIAL, warnings=warnings, extracted_at=datetime.now(timezone.utc))
    return CanonicalSource(source_id=source_id, source_type=SourceType.IMAGE, original_filename=filename, mime_type=MIME_TYPES[suffix], file_size_bytes=len(data), processing_status=ProcessingStatus.PARTIAL, warnings=warnings, units=units, extraction=extraction, original_metadata={"format": suffix.lstrip("."), "ocr_engine": "pytesseract"})
