from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_identity
from app.models import Favorite, Question
from app.schemas.favorite import FavoriteOut
from app.services.auth_service import AuthIdentity

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


def _owner_clause(model, identity: AuthIdentity):
    if identity.user_id is not None:
        return model.user_id == identity.user_id
    return model.guest_session_id == identity.guest_session_id


@router.get("", response_model=list[FavoriteOut])
def list_favorites(
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> list[Favorite]:
    stmt = (
        select(Favorite)
        .options(joinedload(Favorite.question))
        .where(_owner_clause(Favorite, identity))
        .order_by(Favorite.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.post("/{question_id}", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(
    question_id: int,
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> Favorite:
    if not db.get(Question, question_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    existing = db.execute(
        select(Favorite).where(Favorite.question_id == question_id, _owner_clause(Favorite, identity))
    ).scalar_one_or_none()
    if existing:
        return existing
    favorite = Favorite(
        user_id=identity.user_id,
        guest_session_id=None if identity.user_id else identity.guest_session_id,
        question_id=question_id,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    question_id: int,
    identity: AuthIdentity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> None:
    favorite = db.execute(
        select(Favorite).where(Favorite.question_id == question_id, _owner_clause(Favorite, identity))
    ).scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏不存在")
    db.delete(favorite)
    db.commit()
