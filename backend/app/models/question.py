from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    question_no: Mapped[str] = mapped_column(String(50), nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=3, index=True)
    knowledge_area: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    exam = relationship("Exam", back_populates="questions")
    images = relationship("QuestionImage", back_populates="question", cascade="all, delete-orphan")
    records = relationship("UserRecord", back_populates="question", cascade="all, delete-orphan")
    favorite = relationship("Favorite", back_populates="question", cascade="all, delete-orphan", uselist=False)

