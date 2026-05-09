from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam, Favorite, Question, Subject, Tag, User, UserRecord

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    usable_questions = db.execute(
        select(func.count(Question.id)).where(
            Question.quality_status == "ok",
            Question.answer.is_not(None),
            func.length(func.trim(Question.answer)) > 0,
        )
    ).scalar_one()
    return {
        "subjects": db.execute(select(func.count(Subject.id))).scalar_one(),
        "exams": db.execute(select(func.count(Exam.id))).scalar_one(),
        "questions": db.execute(select(func.count(Question.id))).scalar_one(),
        "usable_questions": usable_questions,
        "tags": db.execute(select(func.count(Tag.id))).scalar_one(),
        "users": db.execute(select(func.count(User.id))).scalar_one(),
        "favorites": db.execute(select(func.count(Favorite.id))).scalar_one(),
        "wrong_records": db.execute(select(func.count(UserRecord.id)).where(UserRecord.is_correct.is_(False))).scalar_one(),
    }


@router.get("/by-level")
def stats_by_level(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Subject.level, Subject.name, Subject.id, func.count(Question.id))
        .join(Exam, Exam.subject_id == Subject.id)
        .join(Question, Question.exam_id == Exam.id)
        .where(Question.quality_status == "ok")
        .group_by(Subject.level, Subject.name, Subject.id)
        .order_by(Subject.level, Subject.sort_order, Subject.name)
    ).all()
    return [
        {"level": level, "subject_name": name, "subject_id": subject_id, "question_count": count}
        for level, name, subject_id, count in rows
    ]


@router.get("/wrong-by-tag")
def wrong_by_tag(db: Session = Depends(get_db)) -> list[dict]:
    records = db.execute(select(UserRecord).join(Question).where(UserRecord.is_correct.is_(False))).scalars()
    counts: dict[str, int] = {}
    for record in records:
        for tag in record.question.tags_json or []:
            counts[tag] = counts.get(tag, 0) + 1
    return [{"tag": tag, "wrong_count": count} for tag, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)]


@router.get("/questions-by-year")
def questions_by_year(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Exam.year, func.count(Question.id))
        .join(Question)
        .where(Question.quality_status == "ok")
        .group_by(Exam.year)
        .order_by(Exam.year.desc())
    ).all()
    return [{"year": year, "question_count": count} for year, count in rows]
