from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Subject
from app.schemas.subject import LEVELS, GroupedSubjects, SubjectCreate, SubjectOut, SubjectUpdate

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
def list_subjects(level: str | None = None, enabled: bool | None = True, db: Session = Depends(get_db)) -> list[Subject]:
    stmt = select(Subject)
    if level:
        stmt = stmt.where(Subject.level == level)
    if enabled is not None:
        stmt = stmt.where(Subject.enabled == enabled)
    stmt = stmt.order_by(Subject.sort_order, Subject.level, Subject.name)
    return list(db.execute(stmt).scalars())


@router.get("/grouped", response_model=GroupedSubjects)
def grouped_subjects(db: Session = Depends(get_db)) -> GroupedSubjects:
    subjects = list(
        db.execute(
            select(Subject)
            .where(Subject.enabled.is_(True))
            .order_by(Subject.sort_order, Subject.level, Subject.name)
        ).scalars()
    )
    grouped = {level: [] for level in LEVELS}
    for subject in subjects:
        grouped.setdefault(subject.level, []).append(subject)
    return GroupedSubjects(**{level: grouped.get(level, []) for level in LEVELS})


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Subject:
    subject = Subject(**payload.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.put("/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Subject:
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="科目不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)
    db.commit()
    db.refresh(subject)
    return subject
