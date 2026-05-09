import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exam, ImportBatch, Question, QuestionImage, Subject
from app.schemas.importing import ImportPayload, ImportQuestionIn, ImportResult
from app.utils.hash import question_hash


def subject_code(level: str, name: str) -> str:
    raw = f"{level}-{name}".strip().lower()
    text = re.sub(r"\s+", "-", raw)
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_-]+", "", text)
    return text[:100] or "subject"


def load_import_payload(path: str | Path) -> ImportPayload:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ImportPayload.model_validate(data)


def get_or_create_subject(db: Session, level: str, name: str, subject_id: int | None = None) -> Subject:
    if subject_id:
        subject = db.get(Subject, subject_id)
        if subject:
            return subject
    stmt = select(Subject).where(Subject.level == level, Subject.name == name)
    subject = db.execute(stmt).scalar_one_or_none()
    if subject:
        return subject
    code_base = subject_code(level, name)
    code = code_base
    suffix = 2
    while db.execute(select(Subject).where(Subject.code == code)).scalar_one_or_none():
        code = f"{code_base}-{suffix}"
        suffix += 1
    subject = Subject(level=level, name=name, code=code, enabled=True, sort_order=0)
    db.add(subject)
    db.flush()
    return subject


def get_or_create_exam(db: Session, payload: ImportPayload) -> Exam:
    exam_data = payload.exam.model_dump()
    subject = get_or_create_subject(
        db,
        level=exam_data["level"],
        name=exam_data["exam_name"],
        subject_id=exam_data.get("subject_id"),
    )
    exam_data["subject_id"] = subject.id
    stmt = select(Exam).where(
        Exam.exam_name == exam_data["exam_name"],
        Exam.level == exam_data["level"],
        Exam.year == exam_data["year"],
        Exam.season == exam_data["season"],
        Exam.paper_type == exam_data["paper_type"],
    )
    exam = db.execute(stmt).scalar_one_or_none()
    if exam:
        exam.subject_id = subject.id
        for field in ("source_name", "source_url", "is_memory_version", "remark"):
            value = exam_data.get(field)
            if value not in (None, ""):
                setattr(exam, field, value)
        return exam

    exam = Exam(**exam_data)
    db.add(exam)
    db.flush()
    return exam


def normalize_quality_status(item: ImportQuestionIn) -> str:
    status_value = (item.quality_status or "").strip() or "ok"
    if status_value != "ok":
        return status_value
    if not (item.answer or "").strip():
        return "missing_answer"
    if item.requires_image and not item.images:
        return "missing_image"
    return "ok"


def import_payload(
    db: Session,
    payload: ImportPayload,
    source_file: str,
    source_type: str = "json",
    update_existing: bool = False,
    force_unverified: bool = False,
) -> ImportResult:
    errors: list[str] = []
    success_count = 0
    skipped_count = 0
    updated_count = 0
    failed_count = 0
    seen_hashes: set[str] = set()

    batch = ImportBatch(
        source_file=source_file,
        source_type=source_type,
        total_count=len(payload.questions),
        success_count=0,
        failed_count=0,
        error_log=None,
    )
    db.add(batch)
    db.flush()

    exam = get_or_create_exam(db, payload)

    for index, item in enumerate(payload.questions, start=1):
        try:
            source_hash = question_hash(item.stem, item.options)
            if source_hash in seen_hashes:
                skipped_count += 1
                continue
            seen_hashes.add(source_hash)
            quality_status = normalize_quality_status(item)
            existing = db.execute(select(Question).where(Question.source_hash == source_hash)).scalar_one_or_none()
            if existing:
                if update_existing:
                    existing.answer = item.answer
                    existing.analysis = item.analysis
                    existing.difficulty = item.difficulty
                    existing.knowledge_area = item.knowledge_area
                    existing.tags_json = item.tags
                    existing.question_type = item.question_type
                    existing.question_no = item.question_no
                    existing.source_provider = item.source_provider
                    existing.source_question_id = item.source_question_id
                    existing.source_url = item.source_url
                    existing.quality_status = quality_status
                    existing.requires_image = item.requires_image
                    existing.is_verified = False if force_unverified else item.is_verified
                    if item.images:
                        existing.images.clear()
                        for image in item.images:
                            existing.images.append(QuestionImage(**image.model_dump()))
                    updated_count += 1
                else:
                    skipped_count += 1
                continue

            question = Question(
                exam_id=exam.id,
                question_no=item.question_no,
                question_type=item.question_type,
                stem=item.stem,
                options_json=item.options,
                answer=item.answer,
                analysis=item.analysis,
                difficulty=item.difficulty,
                knowledge_area=item.knowledge_area,
                tags_json=item.tags,
                source_hash=source_hash,
                source_provider=item.source_provider,
                source_question_id=item.source_question_id,
                source_url=item.source_url,
                quality_status=quality_status,
                requires_image=item.requires_image,
                is_verified=False if force_unverified else item.is_verified,
            )
            db.add(question)
            for image in item.images:
                question.images.append(QuestionImage(**image.model_dump()))
            success_count += 1
        except Exception as exc:
            failed_count += 1
            errors.append(f"第 {index} 题导入失败：{exc}")

    batch.success_count = success_count + updated_count
    batch.failed_count = failed_count
    batch.error_log = "\n".join(errors) if errors else None
    db.commit()
    db.refresh(batch)

    return ImportResult(
        batch_id=batch.id,
        total_count=len(payload.questions),
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        updated_count=updated_count,
        errors=errors,
    )
