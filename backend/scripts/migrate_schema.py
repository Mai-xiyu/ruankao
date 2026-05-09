import sys
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Exam, Question  # noqa: E402
from app.models import *  # noqa: E402,F403
from app.services.import_service import get_or_create_subject  # noqa: E402

IMAGE_WORDS = ("图", "表", "拓扑", "日志", "波形", "如下", "截图", "网络结构")


def log(message: str) -> None:
    print(f"[migrate] {message}")


def has_column(table: str, column: str) -> bool:
    inspector = inspect(engine)
    return column in {item["name"] for item in inspector.get_columns(table)}


def run_sql(sql: str, *, ignore_errors: bool = True) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except SQLAlchemyError as exc:
        if ignore_errors:
            log(f"skip: {sql} ({exc.__class__.__name__})")
            return
        raise


def add_column(table: str, column: str, definition: str) -> None:
    if has_column(table, column):
        return
    log(f"add column {table}.{column}")
    run_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}", ignore_errors=False)


def migrate_tables() -> None:
    log("create missing tables")
    Base.metadata.create_all(bind=engine)

    add_column("exams", "subject_id", "INT NULL")

    add_column("questions", "source_provider", "VARCHAR(100) NULL")
    add_column("questions", "source_question_id", "VARCHAR(200) NULL")
    add_column("questions", "source_url", "VARCHAR(500) NULL")
    add_column("questions", "quality_status", "VARCHAR(50) NOT NULL DEFAULT 'ok'")
    add_column("questions", "requires_image", "BOOL NOT NULL DEFAULT 0")

    add_column("favorites", "user_id", "INT NULL")
    add_column("favorites", "guest_session_id", "VARCHAR(64) NULL")

    add_column("user_records", "user_id", "INT NULL")
    add_column("user_records", "guest_session_id", "VARCHAR(64) NULL")

    run_sql("CREATE INDEX ix_exams_subject_id ON exams (subject_id)")
    run_sql("CREATE INDEX ix_questions_quality_status ON questions (quality_status)")
    run_sql("CREATE INDEX ix_questions_source_provider ON questions (source_provider)")
    run_sql("CREATE INDEX ix_questions_source_question_id ON questions (source_question_id)")
    run_sql("CREATE INDEX ix_questions_requires_image ON questions (requires_image)")
    run_sql("ALTER TABLE favorites DROP INDEX uq_favorite_question")
    run_sql("CREATE UNIQUE INDEX uq_favorite_user_question ON favorites (user_id, question_id)")
    run_sql("CREATE UNIQUE INDEX uq_favorite_guest_question ON favorites (guest_session_id, question_id)")
    run_sql("CREATE INDEX ix_user_records_user_id ON user_records (user_id)")
    run_sql("CREATE INDEX ix_user_records_guest_session_id ON user_records (guest_session_id)")


def infer_requires_image(stem: str | None) -> bool:
    text_value = stem or ""
    return any(word in text_value for word in IMAGE_WORDS)


def migrate_data() -> None:
    log("migrate exams to subjects and mark legacy quality")
    with SessionLocal() as db:
        for exam in db.execute(select(Exam)).scalars():
            if exam.subject_id:
                continue
            subject = get_or_create_subject(db, level=exam.level, name=exam.exam_name)
            exam.subject_id = subject.id

        for question in db.execute(select(Question)).scalars():
            answer = (question.answer or "").strip()
            question.requires_image = bool(question.requires_image or infer_requires_image(question.stem))
            if not answer:
                question.quality_status = "low_quality"
            elif question.requires_image and not question.images:
                question.quality_status = "low_quality"
            elif not question.quality_status:
                question.quality_status = "ok"

        db.commit()


def main() -> int:
    migrate_tables()
    migrate_data()
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
