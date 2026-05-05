from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import UserRecord
from app.schemas.question import QuestionOut

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("/wrong")
def wrong_records(db: Session = Depends(get_db)) -> list[dict]:
    records = db.execute(
        select(UserRecord)
        .options(joinedload(UserRecord.question))
        .where(UserRecord.is_correct.is_(False))
        .order_by(UserRecord.answered_at.desc())
    ).scalars()
    return [
        {
            "record_id": record.id,
            "question_id": record.question_id,
            "user_answer": record.user_answer,
            "reviewed": record.reviewed,
            "answered_at": record.answered_at,
            "question": QuestionOut.model_validate(record.question).model_dump(mode="json") if record.question else None,
        }
        for record in records
    ]


@router.post("/{record_id}/reviewed")
def mark_reviewed(record_id: int, db: Session = Depends(get_db)) -> dict:
    record = db.get(UserRecord, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="答题记录不存在")
    record.reviewed = True
    db.commit()
    return {"record_id": record.id, "reviewed": True}
