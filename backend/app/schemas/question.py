from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_path: str
    image_type: str
    caption: str | None = None
    created_at: datetime


class QuestionBase(BaseModel):
    exam_id: int
    question_no: str = Field(max_length=50)
    question_type: str = Field(max_length=50)
    stem: str
    options_json: dict | None = None
    answer: str | None = None
    analysis: str | None = None
    difficulty: int = Field(default=3, ge=1, le=5)
    knowledge_area: str | None = Field(default=None, max_length=100)
    tags_json: list[str] = Field(default_factory=list)
    source_provider: str | None = Field(default=None, max_length=100)
    source_question_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    quality_status: str = Field(default="ok", max_length=50)
    requires_image: bool = False
    is_verified: bool = False

    @field_validator("tags_json")
    @classmethod
    def compact_tags(cls, tags: list[str]) -> list[str]:
        return [tag.strip() for tag in tags if tag and tag.strip()]


class QuestionCreate(QuestionBase):
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)


class QuestionUpdate(BaseModel):
    exam_id: int | None = None
    question_no: str | None = Field(default=None, max_length=50)
    question_type: str | None = Field(default=None, max_length=50)
    stem: str | None = None
    options_json: dict | None = None
    answer: str | None = None
    analysis: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    knowledge_area: str | None = Field(default=None, max_length=100)
    tags_json: list[str] | None = None
    source_provider: str | None = Field(default=None, max_length=100)
    source_question_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    quality_status: str | None = Field(default=None, max_length=50)
    requires_image: bool | None = None
    is_verified: bool | None = None


class QuestionOut(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_hash: str
    images: list[QuestionImageOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
