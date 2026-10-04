from pydantic import BaseModel, Field, field_validator


class EvidenceRef(BaseModel):
    """A source-grounded locator attached to every extracted claim."""

    quote: str = Field(min_length=1)
    source_id: str = "source-1"
    message_index: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    timestamp: str | None = None


class IntelligenceClaim(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list, min_length=1, max_length=5)


class PersonClaim(IntelligenceClaim):
    name: str = Field(min_length=1)
    role: str | None = None


class TaskClaim(IntelligenceClaim):
    owner: str | None = None
    status: str | None = None
    due_date: str | None = None


class DeadlineClaim(IntelligenceClaim):
    date_or_time: str | None = None
    owner: str | None = None


class DecisionClaim(IntelligenceClaim):
    decision: str = Field(min_length=1)


class QuestionClaim(IntelligenceClaim):
    answered: bool = False
    answer: str | None = None


class TechnicalIssueClaim(IntelligenceClaim):
    impact: str | None = None
    status: str | None = None


class DependencyClaim(IntelligenceClaim):
    depends_on: str = Field(min_length=1)
    blocked: bool = False


class ContradictionClaim(IntelligenceClaim):
    claim_a: str = Field(min_length=1)
    claim_b: str = Field(min_length=1)
    resolution: str | None = None


class ExtractedItem(BaseModel):
    kind: str = Field(description="task, deadline, decision, person, question, fact, or instruction")
    text: str
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str


class ExtractionResult(BaseModel):
    summary: str
    items: list[ExtractedItem] = Field(default_factory=list, max_length=20)
    people: list[PersonClaim] = Field(default_factory=list, max_length=50)
    tasks: list[TaskClaim] = Field(default_factory=list, max_length=50)
    deadlines: list[DeadlineClaim] = Field(default_factory=list, max_length=50)
    decisions: list[DecisionClaim] = Field(default_factory=list, max_length=50)
    questions: list[QuestionClaim] = Field(default_factory=list, max_length=50)
    technical_issues: list[TechnicalIssueClaim] = Field(default_factory=list, max_length=50)
    dependencies: list[DependencyClaim] = Field(default_factory=list, max_length=50)
    contradictions: list[ContradictionClaim] = Field(default_factory=list, max_length=50)


class ExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30_000)
    source_type: str = "text"

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value
