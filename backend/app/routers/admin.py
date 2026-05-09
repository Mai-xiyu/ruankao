import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_admin
from app.models import Exam, ImportBatch, Question, QuestionImage, Subject

router = APIRouter(prefix="/api/admin", tags=["admin"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPORT_DIR = BACKEND_DIR / "data" / "exports"
IMAGE_WORDS = ("图", "表", "拓扑", "日志", "波形", "如下", "截图", "网络结构")


class CleanupApplyRequest(BaseModel):
    confirm: bool = False
    mode: Literal["isolate", "delete"] = "isolate"
    backup: bool = True
    stem_min_length: int = Field(default=8, ge=1, le=200)


class CleanupReport(BaseModel):
    total_questions: int
    candidate_count: int
    by_reason: dict[str, int]
    backup_file: str | None = None
    applied: bool = False
    mode: str | None = None


def _has_answer(question: Question) -> bool:
    return bool((question.answer or "").strip())


def _option_count(question: Question) -> int:
    if not isinstance(question.options_json, dict):
        return 0
    return len([value for value in question.options_json.values() if str(value or "").strip()])


def _needs_image_by_stem(question: Question) -> bool:
    stem = question.stem or ""
    return any(word in stem for word in IMAGE_WORDS)


def _quality_reasons(question: Question) -> list[str]:
    reasons: list[str] = []
    if not _has_answer(question):
        reasons.append("missing_answer")
    if question.question_type == "single_choice" and _option_count(question) < 2:
        reasons.append("single_choice_missing_options")
    if len((question.stem or "").strip()) < 8:
        reasons.append("stem_too_short")
    if question.quality_status != "ok":
        reasons.append(f"quality_status:{question.quality_status}")
    if (question.requires_image or _needs_image_by_stem(question)) and not question.images:
        reasons.append("missing_required_image")
    if (question.source_provider or "").lower() in {"ai", "deepseek", "pdf-ai"} and not question.is_verified:
        reasons.append("unverified_ai_draft")
    return reasons


def _find_cleanup_candidates(db: Session) -> tuple[list[tuple[Question, list[str]]], dict[str, int]]:
    questions = list(db.execute(select(Question).options(joinedload(Question.images))).unique().scalars())
    candidates: list[tuple[Question, list[str]]] = []
    by_reason: dict[str, int] = {}
    for question in questions:
        reasons = _quality_reasons(question)
        if not reasons:
            continue
        candidates.append((question, reasons))
        for reason in reasons:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return candidates, by_reason


def _backup_current_bank(db: Session) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORT_DIR / f"cleanup_backup_{timestamp}.json"
    data = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "subjects": [
            {
                "id": item.id,
                "level": item.level,
                "name": item.name,
                "code": item.code,
                "enabled": item.enabled,
                "sort_order": item.sort_order,
            }
            for item in db.execute(select(Subject).order_by(Subject.id)).scalars()
        ],
        "exams": [
            {
                "id": item.id,
                "subject_id": item.subject_id,
                "exam_name": item.exam_name,
                "level": item.level,
                "year": item.year,
                "season": item.season,
                "paper_type": item.paper_type,
                "source_name": item.source_name,
                "source_url": item.source_url,
            }
            for item in db.execute(select(Exam).order_by(Exam.id)).scalars()
        ],
        "questions": [
            {
                "id": item.id,
                "exam_id": item.exam_id,
                "question_no": item.question_no,
                "question_type": item.question_type,
                "stem": item.stem,
                "options_json": item.options_json,
                "answer": item.answer,
                "analysis": item.analysis,
                "difficulty": item.difficulty,
                "knowledge_area": item.knowledge_area,
                "tags_json": item.tags_json,
                "source_hash": item.source_hash,
                "source_provider": item.source_provider,
                "source_question_id": item.source_question_id,
                "source_url": item.source_url,
                "quality_status": item.quality_status,
                "requires_image": item.requires_image,
                "is_verified": item.is_verified,
            }
            for item in db.execute(select(Question).order_by(Question.id)).scalars()
        ],
        "question_images": [
            {
                "id": item.id,
                "question_id": item.question_id,
                "image_path": item.image_path,
                "image_type": item.image_type,
                "caption": item.caption,
            }
            for item in db.execute(select(QuestionImage).order_by(QuestionImage.id)).scalars()
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@router.post("/cleanup/preview", response_model=CleanupReport)
def cleanup_preview(
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CleanupReport:
    candidates, by_reason = _find_cleanup_candidates(db)
    total_questions = db.execute(select(func.count(Question.id))).scalar_one()
    return CleanupReport(total_questions=total_questions, candidate_count=len(candidates), by_reason=by_reason)


@router.post("/cleanup/apply", response_model=CleanupReport)
def cleanup_apply(
    payload: CleanupApplyRequest,
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CleanupReport:
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要 confirm=true 才会执行清理")
    candidates, by_reason = _find_cleanup_candidates(db)
    backup_file = str(_backup_current_bank(db)) if payload.backup else None

    if payload.mode == "delete":
        for question, _ in candidates:
            db.delete(question)
        db.flush()
        empty_exams = db.execute(
            select(Exam).outerjoin(Question).group_by(Exam.id).having(func.count(Question.id) == 0)
        ).scalars()
        for exam in empty_exams:
            db.delete(exam)
    else:
        for question, _ in candidates:
            question.quality_status = "low_quality"

    db.commit()
    total_questions = db.execute(select(func.count(Question.id))).scalar_one()
    return CleanupReport(
        total_questions=total_questions,
        candidate_count=len(candidates),
        by_reason=by_reason,
        backup_file=backup_file,
        applied=True,
        mode=payload.mode,
    )


@router.get("/import-batches")
def import_batches(
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())).scalars()
    return [
        {
            "id": row.id,
            "source_file": row.source_file,
            "source_type": row.source_type,
            "total_count": row.total_count,
            "success_count": row.success_count,
            "failed_count": row.failed_count,
            "error_log": row.error_log,
            "created_at": row.created_at,
        }
        for row in rows
    ]
