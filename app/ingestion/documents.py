"""Docling-backed PDF, DOCX, and PPTX ingestion adapter."""

from datetime import datetime, timezone
from io import BytesIO
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any
import zipfile

from app.source.models import CanonicalSource, ContentType, ContentUnit, ExtractionMetadata, ProcessingStatus, SourceLocator, SourceType

SUPPORTED_EXTENSIONS = {".pdf": SourceType.PDF, ".docx": SourceType.DOCX, ".pptx": SourceType.PPTX}
MIME_TYPES = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024


class DocumentIngestionError(RuntimeError):
    """A document could not be converted into canonical content."""


class DoclingUnavailable(DocumentIngestionError):
    """Docling is not installed in the active runtime."""


def validate_document_payload(data: bytes, *, filename: str, declared_mime_type: str | None = None) -> None:
    """Validate extension, meaningful declared MIME type, and file signature."""
    suffix = Path(filename).suffix.casefold()
    expected_mime = MIME_TYPES.get(suffix)
    if expected_mime is None:
        raise DocumentIngestionError("Only PDF, DOCX, and PPTX files are supported in Phase 3.")
    if len(data) > MAX_DOCUMENT_SIZE_BYTES:
        raise DocumentIngestionError(f"Documents must be {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MiB or smaller.")
    if not data:
        raise DocumentIngestionError("The document is empty.")
    normalized_mime = (declared_mime_type or "").split(";", 1)[0].strip().casefold()
    if normalized_mime and normalized_mime != "application/octet-stream" and normalized_mime != expected_mime:
        raise DocumentIngestionError(f"The declared MIME type does not match {suffix}.")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentIngestionError("The file does not have a valid PDF signature.")
        return
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise DocumentIngestionError("The OOXML document is not a valid ZIP container.") from exc
    if "[Content_Types].xml" not in names:
        raise DocumentIngestionError("The OOXML document is missing [Content_Types].xml.")
    required_prefix = "word/" if suffix == ".docx" else "ppt/"
    if not any(name.startswith(required_prefix) for name in names):
        raise DocumentIngestionError(f"The file signature does not match {suffix}.")


def _source_id(data: bytes, filename: str) -> str:
    return f"document-{hashlib.sha256(filename.encode('utf-8') + b'\0' + data).hexdigest()[:24]}"


def _item_text(item: Any, document: Any) -> str:
    text = getattr(item, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    exporter = getattr(item, "export_to_markdown", None)
    if callable(exporter):
        try:
            exported = exporter(doc=document)
            if isinstance(exported, str):
                return exported
        except TypeError:
            exported = exporter()
            if isinstance(exported, str):
                return exported
    return ""


def _item_locator(item: Any, source_id: str, position: int, level: int, source_type: SourceType) -> tuple[SourceLocator, dict[str, Any]]:
    provenance = getattr(item, "prov", None) or []
    first = provenance[0] if provenance else None
    page_number = getattr(first, "page_no", None) if first else None
    charspan = getattr(first, "charspan", None) if first else None
    metadata: dict[str, Any] = {"docling_level": level}
    if charspan and len(charspan) == 2:
        metadata["charspan"] = list(charspan)
    bbox = getattr(first, "bbox", None) if first else None
    if bbox is not None:
        metadata["bbox"] = bbox.model_dump(mode="json") if hasattr(bbox, "model_dump") else str(bbox)
    return SourceLocator(source_id=source_id, page_number=None if source_type is SourceType.PPTX else page_number, slide_number=page_number if source_type is SourceType.PPTX else None, character_start=charspan[0] if charspan else None, character_end=charspan[1] if charspan else None, metadata=metadata), metadata


def _content_type(label: str) -> ContentType:
    normalized = label.casefold()
    if "table" in normalized:
        return ContentType.TABLE
    if "heading" in normalized or "title" in normalized or "section" in normalized:
        return ContentType.HEADING
    if normalized in {"text", "paragraph", "list_item", "caption", "footnote"}:
        return ContentType.PARAGRAPH
    return ContentType.OTHER


def _failed_source(filename: str, data: bytes, message: str) -> CanonicalSource:
    status = ProcessingStatus.FAILED
    return CanonicalSource(
        source_id=_source_id(data, filename),
        source_type=SUPPORTED_EXTENSIONS.get(Path(filename).suffix.casefold(), SourceType.UNKNOWN),
        original_filename=filename,
        mime_type=MIME_TYPES.get(Path(filename).suffix.casefold()),
        file_size_bytes=len(data),
        processing_status=status,
        errors=[message],
        extraction=ExtractionMetadata(method="docling", tool="docling", status=status, errors=[message], extracted_at=datetime.now(timezone.utc)),
    )


def convert_document_bytes(data: bytes, *, filename: str, declared_mime_type: str | None = None, converter: Any | None = None) -> CanonicalSource:
    """Convert one supported document using Docling and preserve page provenance."""
    suffix = Path(filename).suffix.casefold()
    source_type = SUPPORTED_EXTENSIONS.get(suffix)
    if source_type is None:
        raise DocumentIngestionError("Only PDF, DOCX, and PPTX files are supported in Phase 3.")
    if not data:
        return _failed_source(filename, data, "The document is empty.")
    validate_document_payload(data, filename=filename, declared_mime_type=declared_mime_type)
    if converter is None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise DoclingUnavailable("Docling is not installed in the active runtime.") from exc
        converter = DocumentConverter()
    source_id = _source_id(data, filename)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(data)
            temporary.flush()
        result = converter.convert(temporary_path)
    except Exception as exc:
        return _failed_source(filename, data, f"Docling conversion failed: {type(exc).__name__}.")
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
    document = getattr(result, "document", None)
    if document is None:
        return _failed_source(filename, data, "Docling returned no document.")
    units: list[ContentUnit] = []
    warnings: list[str] = []
    iterator = getattr(document, "iterate_items", None)
    if callable(iterator):
        for position, pair in enumerate(iterator()):
            item, level = pair
            text = _item_text(item, document)
            if not text.strip():
                continue
            label = str(getattr(getattr(item, "label", None), "value", getattr(item, "label", "other")))
            locator, metadata = _item_locator(item, source_id, position, level, source_type)
            units.append(ContentUnit(source_id=source_id, content_type=_content_type(label), text=text, position=len(units), locator=locator, metadata={"docling_label": label, **metadata}))
    if not units:
        exporter = getattr(document, "export_to_text", None)
        fallback_text = exporter() if callable(exporter) else ""
        if fallback_text.strip():
            warnings.append("Docling item iteration returned no structured items; plain text fallback was used.")
            units.append(ContentUnit(source_id=source_id, content_type=ContentType.PARAGRAPH, text=fallback_text, position=0, locator=SourceLocator(source_id=source_id, metadata={"fallback": "export_to_text"})))
    status = ProcessingStatus.COMPLETED if units and not warnings else ProcessingStatus.PARTIAL if units else ProcessingStatus.FAILED
    extraction = ExtractionMetadata(method="docling", tool="docling", status=status, warnings=warnings, extracted_at=datetime.now(timezone.utc), metadata={"format": suffix.lstrip(".")})
    return CanonicalSource(source_id=source_id, source_type=source_type, original_filename=filename, mime_type=MIME_TYPES[suffix], file_size_bytes=len(data), processing_status=status, warnings=warnings, units=units, extraction=extraction, original_metadata={"format": suffix.lstrip("."), "unit_count": len(units)})
