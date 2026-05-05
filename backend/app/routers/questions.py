from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam, Question
from app.schemas.question import QuestionCreate, QuestionOut, QuestionUpdate
from app.utils.hash import question_hash

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.get("", response_model=list[QuestionOut])
def list_questions(
    year: int | None = None,
    season: str | None = None,
    paper_type: str | None = None,
    knowledge_area: str | None = None,
    tag: str | None = None,
    difficulty: int | None = Query(default=None, ge=1, le=5),
    keyword: str | None = None,
    question_type: str | None = None,
    is_verified: bool | None = None,
    has_answer: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = select(Question).join(Exam)
    if year is not None:
        stmt = stmt.where(Exam.year == year)
    if season:
        stmt = stmt.where(Exam.season == season)
    if paper_type:
        stmt = stmt.where(Exam.paper_type == paper_type)
    if knowledge_area:
        stmt = stmt.where(Question.knowledge_area == knowledge_area)
    if tag:
        stmt = stmt.where(cast(Question.tags_json, String).like(f'%"{tag}"%'))
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Question.stem.like(like), Question.analysis.like(like)))
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    if is_verified is not None:
        stmt = stmt.where(Question.is_verified == is_verified)
    if has_answer is True:
        stmt = stmt.where(Question.answer.is_not(None), func.length(func.trim(Question.answer)) > 0)
    elif has_answer is False:
        stmt = stmt.where(or_(Question.answer.is_(None), func.length(func.trim(Question.answer)) == 0))
    stmt = stmt.order_by(Question.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db)) -> Question:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    return question


@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)) -> Question:
    if not db.get(Exam, payload.exam_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    source_hash = payload.source_hash or question_hash(payload.stem, payload.options_json)
    existing = db.execute(select(Question).where(Question.source_hash == source_hash)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="重复题目已存在")
    data = payload.model_dump(exclude={"source_hash"})
    question = Question(**data, source_hash=source_hash)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdate, db: Session = Depends(get_db)) -> Question:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    data = payload.model_dump(exclude_unset=True)
    if "exam_id" in data and not db.get(Exam, data["exam_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    for field, value in data.items():
        setattr(question, field, value)
    if "stem" in data or "options_json" in data:
        new_hash = question_hash(question.stem, question.options_json)
        existing = db.execute(select(Question).where(Question.source_hash == new_hash, Question.id != question.id)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="更新后会与已有题目重复")
        question.source_hash = new_hash
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, db: Session = Depends(get_db)) -> None:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    db.delete(question)
    db.commit()
