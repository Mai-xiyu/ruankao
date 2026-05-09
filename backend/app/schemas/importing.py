from pydantic import BaseModel, Field, field_validator

from app.schemas.exam import ExamCreate


class ImportQuestionImageIn(BaseModel):
    image_path: str = Field(max_length=500)
    image_type: str = Field(default="other", max_length=50)
    caption: str | None = Field(default=None, max_length=500)


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
    source_provider: str | None = Field(default=None, max_length=100)
    source_question_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    quality_status: str = Field(default="ok", max_length=50)
    requires_image: bool = False
    is_verified: bool = False
    images: list[ImportQuestionImageIn] = Field(default_factory=list)

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
