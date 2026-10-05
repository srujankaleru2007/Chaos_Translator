from pydantic import BaseModel, Field, field_validator


class EvidenceRef(BaseModel):
    """A source-grounded locator attached to every extracted claim."""

    quote: str = Field(min_length=1)
    source_id: str = "source-1"
    message_index: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    timestamp: str | None = None
    page_number: int | None = Field(default=None, ge=1)


class IntelligenceClaim(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=5)
    uncertain: bool = False


class PersonClaim(IntelligenceClaim):
    name: str = Field(min_length=1)
    role: str | None = None


class TaskClaim(IntelligenceClaim):
    owner: str | None = None
    status: str | None = None
    due_date: str | None = None
    priority: str | None = None
    dependencies: list[str] = Field(default_factory=list, max_length=10)


class DeadlineClaim(IntelligenceClaim):
    date_or_time: str | None = None
    owner: str | None = None
    deadline_type: str | None = None
    timezone: str | None = None
    confirmation_status: str | None = None


class DecisionClaim(IntelligenceClaim):
    decision: str = Field(min_length=1)
    decided_by: str | None = None
    decided_at: str | None = None


class QuestionClaim(IntelligenceClaim):
    answered: bool = False
    answer: str | None = None


class TechnicalIssueClaim(IntelligenceClaim):
    impact: str | None = None
    status: str | None = None
    component: str | None = None
    resolution: str | None = None


class DependencyClaim(IntelligenceClaim):
    depends_on: str = Field(min_length=1)
    blocked: bool = False
    dependent_task: str | None = None
    relationship: str | None = None


class ContradictionClaim(IntelligenceClaim):
    claim_a: str = Field(min_length=1)
    claim_b: str = Field(min_length=1)
    resolution: str | None = None
    resolution_status: str = "unresolved"
    authoritative_claim: str | None = None


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
    provider: str | None = None
    model: str | None = None
    cloud_fallback_used: bool = False
    correlation_id: str | None = None
    partial: bool = False
    chunks_processed: int = 1
    chunks_total: int = 1
    failed_chunks: list[int] = Field(default_factory=list, max_length=100)


class PeopleExtractionResult(BaseModel):
    """The narrow contract exposed to local Qwen name extraction."""

    people: list[PersonClaim] = Field(default_factory=list, max_length=50)


class ExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    source_type: str = "text"
    cloud_consent: bool = False

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value


class BriefingAudioRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value
