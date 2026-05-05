from pydantic import BaseModel, Field, field_validator

from app.schemas.exam import ExamCreate


class ImportQuestionIn(BaseModel):
    question_no: str = Field(max_length=50)
    question_type: str = Field(max_length=50)
    stem: str
    options: dict | None = None
    answer: str | None = None
    analysis: str | None = None
    difficulty: int = Field(default=3, ge=1, le=5)
    knowledge_area: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)
    is_verified: bool = False

    @field_validator("tags")
    @classmethod
    def compact_tags(cls, tags: list[str]) -> list[str]:
        return [tag.strip() for tag in tags if tag and tag.strip()]


class ImportPayload(BaseModel):
    exam: ExamCreate
    questions: list[ImportQuestionIn]


class ImportResult(BaseModel):
    batch_id: int
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    updated_count: int
    errors: list[str] = Field(default_factory=list)

