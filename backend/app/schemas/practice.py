from pydantic import BaseModel, Field

from app.schemas.question import QuestionOut


class PracticeSubmit(BaseModel):
    question_id: int
    user_answer: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)


class PracticeSubmitResult(BaseModel):
    record_id: int
    question_id: int
    is_correct: bool
    correct_answer: str | None
    analysis: str | None
    knowledge_area: str | None
    tags: list[str]


class PracticeQuestion(QuestionOut):
    pass
