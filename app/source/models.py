"""The source-grounded contract shared by every future ingestion adapter."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(StrEnum):
    WHATSAPP = "whatsapp"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"
    AUDIO = "audio"
    UNKNOWN = "unknown"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ContentType(StrEnum):
    MESSAGE = "message"
    SYSTEM = "system"
    MEDIA = "media"
    DELETED = "deleted"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    OCR_BLOCK = "ocr_block"
    TRANSCRIPT_SEGMENT = "transcript_segment"
    OTHER = "other"


class SourceLocator(BaseModel):
    """A typed, extensible pointer to a region in the original source."""

    model_config = ConfigDict(extra="allow")

    source_id: str = Field(min_length=1)
    message_index: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, ge=1)
    paragraph_index: int | None = Field(default=None, ge=0)
    block_index: int | None = Field(default=None, ge=0)
    slide_number: int | None = Field(default=None, ge=1)
    segment_index: int | None = Field(default=None, ge=0)
    timestamp_start: datetime | None = None
    timestamp_end: datetime | None = None
    timestamp_start_seconds: float | None = Field(default=None, ge=0)
    timestamp_end_seconds: float | None = Field(default=None, ge=0)
    character_start: int | None = Field(default=None, ge=0)
    character_end: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceLocator":
        if self.timestamp_start and self.timestamp_end and self.timestamp_end < self.timestamp_start:
            raise ValueError("timestamp_end must not precede timestamp_start")
        if self.timestamp_start_seconds is not None and self.timestamp_end_seconds is not None and self.timestamp_end_seconds < self.timestamp_start_seconds:
            raise ValueError("timestamp_end_seconds must not precede timestamp_start_seconds")
        if self.character_start is not None and self.character_end is not None and self.character_end < self.character_start:
            raise ValueError("character_end must not precede character_start")
        return self


class ContentUnit(BaseModel):
    """An ordered, source-owned piece of normalized extracted content."""

    model_config = ConfigDict(extra="allow")

    unit_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    source_id: str = Field(min_length=1)
    content_type: ContentType
    text: str = ""
    position: int = Field(ge=0)
    timestamp: datetime | None = None
    sender_or_speaker: str | None = None
    locator: SourceLocator
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source_reference(self) -> "ContentUnit":
        if self.locator.source_id != self.source_id:
            raise ValueError("locator.source_id must match content unit source_id")
        return self


class ExtractionMetadata(BaseModel):
    method: str | None = None
    tool: str | None = None
    extracted_at: datetime | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    warnings: list[str] = Field(default_factory=list, max_length=100)
    errors: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalSource(BaseModel):
    """Canonical source document shared by all ingestion adapters."""

    model_config = ConfigDict(extra="allow")

    source_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    source_type: SourceType = SourceType.UNKNOWN
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    original_metadata: dict[str, Any] = Field(default_factory=dict)
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    warnings: list[str] = Field(default_factory=list, max_length=100)
    errors: list[str] = Field(default_factory=list, max_length=100)
    units: list[ContentUnit] = Field(default_factory=list, max_length=100_000)
    extraction: ExtractionMetadata = Field(default_factory=ExtractionMetadata)
    workspace_id: str | None = None

    @model_validator(mode="after")
    def validate_units(self) -> "CanonicalSource":
        unit_ids = [unit.unit_id for unit in self.units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("content unit IDs must be unique within a source")
        positions = [unit.position for unit in self.units]
        if positions != sorted(positions):
            raise ValueError("content units must be ordered by position")
        if any(unit.source_id != self.source_id for unit in self.units):
            raise ValueError("every content unit must belong to the source")
        return self
