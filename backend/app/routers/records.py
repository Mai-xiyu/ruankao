from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_identity
from app.models import UserRecord
from app.schemas.question import QuestionOut
from app.services.auth_service import AuthIdentity

router = APIRouter(prefix="/api/records", tags=["records"])


def _owner_clause(model, identity: AuthIdentity):
    if identity.user_id is not None:
        return model.user_id == identity.user_id
    return model.guest_session_id == identity.guest_session_id


@router.get("/wrong")
def wrong_records(
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> list[dict]:
    records = db.execute(
        select(UserRecord)
        .options(joinedload(UserRecord.question))
        .where(UserRecord.is_correct.is_(False), _owner_clause(UserRecord, identity))
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
def mark_reviewed(
    record_id: int,
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> dict:
    record = db.execute(select(UserRecord).where(UserRecord.id == record_id, _owner_clause(UserRecord, identity))).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="答题记录不存在")
    record.reviewed = True
    db.commit()
    return {"record_id": record.id, "reviewed": True}
