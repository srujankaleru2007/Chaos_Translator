from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    kind: str = Field(description="task, deadline, decision, person, question, fact, or instruction")
    text: str
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str


class ExtractionResult(BaseModel):
    summary: str
    items: list[ExtractedItem] = Field(default_factory=list, max_length=20)


class ExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30_000)
    source_type: str = "text"
