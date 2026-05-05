from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Favorite, Question
from app.schemas.favorite import FavoriteOut

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteOut])
def list_favorites(db: Session = Depends(get_db)) -> list[Favorite]:
    return list(db.execute(select(Favorite).options(joinedload(Favorite.question)).order_by(Favorite.created_at.desc())).scalars())


@router.post("/{question_id}", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(question_id: int, db: Session = Depends(get_db)) -> Favorite:
    if not db.get(Question, question_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    existing = db.execute(select(Favorite).where(Favorite.question_id == question_id)).scalar_one_or_none()
    if existing:
        return existing
    favorite = Favorite(question_id=question_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(question_id: int, db: Session = Depends(get_db)) -> None:
    favorite = db.execute(select(Favorite).where(Favorite.question_id == question_id)).scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏不存在")
    db.delete(favorite)
    db.commit()

