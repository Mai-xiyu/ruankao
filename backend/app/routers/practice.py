from random import randint

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam, Question, UserRecord
from app.schemas.practice import PracticeSubmit, PracticeSubmitResult
from app.schemas.question import QuestionOut
from app.utils.hash import normalize_text

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _answer_matches(expected: str | None, actual: str | None) -> bool:
    return normalize_text(expected or "") == normalize_text(actual or "")


def _random_questions(stmt, limit: int, db: Session) -> list[Question]:
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    if total <= 0:
        return []
    offset = randint(0, max(0, total - limit))
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars())


@router.get("/random", response_model=list[QuestionOut])
def random_questions(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)) -> list[Question]:
    stmt = select(Question).order_by(func.rand())
    return list(db.execute(stmt.limit(limit)).scalars())


@router.get("/by-year/{year}", response_model=list[QuestionOut])
def practice_by_year(year: int, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[Question]:
    stmt = select(Question).join(Exam).where(Exam.year == year).order_by(func.rand())
    return list(db.execute(stmt.limit(limit)).scalars())


@router.get("/by-tag/{tag}", response_model=list[QuestionOut])
def practice_by_tag(tag: str, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[Question]:
    stmt = select(Question).where(cast(Question.tags_json, String).like(f'%"{tag}"%')).order_by(func.rand())
    return list(db.execute(stmt.limit(limit)).scalars())


@router.get("/wrong", response_model=list[QuestionOut])
def practice_wrong(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[Question]:
    stmt = (
        select(Question)
        .join(UserRecord)
        .where(UserRecord.is_correct.is_(False), UserRecord.reviewed.is_(False))
        .distinct()
        .order_by(func.rand())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


@router.post("/submit", response_model=PracticeSubmitResult)
def submit_answer(payload: PracticeSubmit, db: Session = Depends(get_db)) -> PracticeSubmitResult:
    question = db.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    is_correct = _answer_matches(question.answer, payload.user_answer)
    record = UserRecord(
        question_id=question.id,
        user_answer=payload.user_answer,
        is_correct=is_correct,
        duration_seconds=payload.duration_seconds,
        reviewed=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return PracticeSubmitResult(
        record_id=record.id,
        question_id=question.id,
        is_correct=is_correct,
        correct_answer=question.answer,
        analysis=question.analysis,
        knowledge_area=question.knowledge_area,
        tags=question.tags_json or [],
    )

