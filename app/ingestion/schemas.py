from pydantic import BaseModel, Field


class WhatsAppIngestionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    filename: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
