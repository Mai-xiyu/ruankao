from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.subject import SubjectOut


class ExamBase(BaseModel):
    subject_id: int | None = None
    exam_name: str = Field(max_length=100)
    level: str = Field(max_length=50)
    year: int = Field(ge=1990, le=2100)
    season: str = Field(max_length=50)
    paper_type: str = Field(max_length=100)
    source_name: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=500)
    is_memory_version: bool = False
    remark: str | None = None


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    subject_id: int | None = None
    exam_name: str | None = Field(default=None, max_length=100)
    level: str | None = Field(default=None, max_length=50)
    year: int | None = Field(default=None, ge=1990, le=2100)
    season: str | None = Field(default=None, max_length=50)
    paper_type: str | None = Field(default=None, max_length=100)
    source_name: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=500)
    is_memory_version: bool | None = None
    remark: str | None = None


class ExamOut(ExamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: SubjectOut | None = None
    created_at: datetime
    updated_at: datetime
