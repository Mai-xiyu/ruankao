from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_admin
from app.models import Exam, Subject
from app.schemas.exam import ExamCreate, ExamOut, ExamUpdate

router = APIRouter(prefix="/api/exams", tags=["exams"])


@router.get("", response_model=list[ExamOut])
def list_exams(
    subject_id: int | None = None,
    level: str | None = None,
    exam_name: str | None = None,
    db: Session = Depends(get_db),
) -> list[Exam]:
    stmt = select(Exam).options(joinedload(Exam.subject)).outerjoin(Subject)
    if subject_id is not None:
        stmt = stmt.where(Exam.subject_id == subject_id)
    if level:
        stmt = stmt.where(or_(Subject.level == level, Exam.level == level))
    if exam_name:
        stmt = stmt.where(Exam.exam_name == exam_name)
    stmt = stmt.order_by(Exam.year.desc(), Exam.season.desc(), Exam.paper_type)
    return list(db.execute(stmt).scalars())


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: int, db: Session = Depends(get_db)) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    return exam


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Exam:
    data = payload.model_dump()
    if data.get("subject_id"):
        subject = db.get(Subject, data["subject_id"])
        if not subject:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="科目不存在")
        data["level"] = subject.level
    exam = Exam(**data)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.put("/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("subject_id"):
        subject = db.get(Subject, data["subject_id"])
        if not subject:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="科目不存在")
        data.setdefault("level", subject.level)
    for field, value in data.items():
        setattr(exam, field, value)
    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="考试不存在")
    db.delete(exam)
    db.commit()
