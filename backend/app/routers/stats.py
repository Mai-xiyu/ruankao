from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam, Favorite, Question, Tag, UserRecord

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return {
        "exams": db.execute(select(func.count(Exam.id))).scalar_one(),
        "questions": db.execute(select(func.count(Question.id))).scalar_one(),
        "tags": db.execute(select(func.count(Tag.id))).scalar_one(),
        "favorites": db.execute(select(func.count(Favorite.id))).scalar_one(),
        "wrong_records": db.execute(select(func.count(UserRecord.id)).where(UserRecord.is_correct.is_(False))).scalar_one(),
    }


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
        .group_by(Exam.year)
        .order_by(Exam.year.desc())
    ).all()
    return [{"year": year, "question_count": count} for year, count in rows]

