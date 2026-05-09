from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.question import QuestionOut


class FavoriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    guest_session_id: str | None = None
    question_id: int
    created_at: datetime
    question: QuestionOut | None = None
