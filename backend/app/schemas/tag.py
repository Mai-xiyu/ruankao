from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    name: str = Field(max_length=100)
    category: str | None = Field(default="knowledge", max_length=100)


class TagOut(TagCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime

