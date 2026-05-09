from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_identity
from app.models import Exam, Question, Subject, UserRecord
from app.schemas.practice import PracticeSubmit, PracticeSubmitResult
from app.schemas.question import QuestionOut
from app.services.auth_service import AuthIdentity
from app.utils.hash import normalize_text

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _answer_matches(expected: str | None, actual: str | None) -> bool:
    return normalize_text(expected or "") == normalize_text(actual or "")


def _owner_clause(model, identity: AuthIdentity):
    if identity.user_id is not None:
        return model.user_id == identity.user_id
    return model.guest_session_id == identity.guest_session_id


def _usable_question_stmt(subject_id: int | None = None, level: str | None = None):
    stmt = select(Question).join(Exam).outerjoin(Subject).where(
        Question.quality_status == "ok",
        Question.answer.is_not(None),
        func.length(func.trim(Question.answer)) > 0,
    )
    if subject_id is not None:
        stmt = stmt.where(Exam.subject_id == subject_id)
    if level:
        stmt = stmt.where(or_(Subject.level == level, Exam.level == level))
    return stmt


@router.get("/random", response_model=list[QuestionOut])
def random_questions(
    limit: int = Query(default=10, ge=1, le=100),
    subject_id: int | None = None,
    level: str | None = None,
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = _usable_question_stmt(subject_id=subject_id, level=level).order_by(func.rand()).limit(limit)
    return list(db.execute(stmt).scalars())


@router.get("/by-year/{year}", response_model=list[QuestionOut])
def practice_by_year(
    year: int,
    limit: int = Query(default=20, ge=1, le=100),
    subject_id: int | None = None,
    level: str | None = None,
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = (
        _usable_question_stmt(subject_id=subject_id, level=level)
        .where(Exam.year == year)
        .order_by(func.rand())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


@router.get("/by-tag/{tag}", response_model=list[QuestionOut])
def practice_by_tag(
    tag: str,
    limit: int = Query(default=20, ge=1, le=100),
    subject_id: int | None = None,
    level: str | None = None,
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = (
        _usable_question_stmt(subject_id=subject_id, level=level)
        .where(cast(Question.tags_json, String).like(f'%"{tag}"%'))
        .order_by(func.rand())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


@router.get("/wrong", response_model=list[QuestionOut])
def practice_wrong(
    limit: int = Query(default=20, ge=1, le=100),
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = (
        select(Question)
        .join(UserRecord)
        .where(UserRecord.is_correct.is_(False), UserRecord.reviewed.is_(False), _owner_clause(UserRecord, identity))
        .distinct()
        .order_by(func.rand())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


@router.post("/submit", response_model=PracticeSubmitResult)
def submit_answer(
    payload: PracticeSubmit,
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> PracticeSubmitResult:
    question = db.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    is_correct = _answer_matches(question.answer, payload.user_answer)
    record = UserRecord(
        user_id=identity.user_id,
        guest_session_id=None if identity.user_id else identity.guest_session_id,
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
