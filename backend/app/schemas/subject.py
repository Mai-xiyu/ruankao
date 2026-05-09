from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


LEVELS = ("高级", "中级", "初级")


class SubjectBase(BaseModel):
    level: str = Field(max_length=50)
    name: str = Field(max_length=100)
    code: str = Field(max_length=100)
    enabled: bool = True
    sort_order: int = 0


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    level: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None
    sort_order: int | None = None


class SubjectOut(SubjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class GroupedSubjects(BaseModel):
    高级: list[SubjectOut] = Field(default_factory=list)
    中级: list[SubjectOut] = Field(default_factory=list)
    初级: list[SubjectOut] = Field(default_factory=list)
