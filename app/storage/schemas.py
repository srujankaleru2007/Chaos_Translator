"""Application-owned document contracts stored in MongoDB."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.inference.schemas import ExtractionResult
from app.source.models import CanonicalSource

SourceDocument = CanonicalSource


class ExtractionDocument(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    workspace_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    result: ExtractionResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def mongo_document(model: BaseModel) -> dict[str, Any]:
    """Serialize a document without leaking a Pydantic object into BSON."""
    return model.model_dump(mode="python")
