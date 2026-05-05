"""
从 full_export.json 导入全部题目到数据库。

用法:
    python scripts/import_full_export.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models import Exam, Question  # noqa: E402
from app.utils.hash import question_hash  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main():
    export_path = BACKEND_DIR / "data" / "full_export.json"
    if not export_path.exists():
        print(f"文件不存在: {export_path}")
        return 1

    data = json.loads(export_path.read_text("utf-8"))
    exams_data = data["exams"]
    questions_data = data["questions"]

    # Create tables
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Upsert exams
        exam_map = {}  # (year, season, paper_type) -> exam_id
        for ed in exams_data:
            key = (ed["year"], ed["season"], ed["paper_type"])
            existing = db.execute(
                select(Exam).where(
                    Exam.year == ed["year"],
                    Exam.season == ed["season"],
                    Exam.paper_type == ed["paper_type"],
                )
            ).scalar_one_or_none()

            if existing:
                exam_map[key] = existing.id
            else:
                exam = Exam(**ed)
                db.add(exam)
                db.flush()
                exam_map[key] = exam.id

        db.commit()
        print(f"Exams: {len(exam_map)}")

        # Insert questions
        inserted = 0
        skipped = 0
        for qd in questions_data:
            key = (qd["exam_year"], qd["exam_season"], qd["exam_paper_type"])
            exam_id = exam_map.get(key)
            if not exam_id:
                skipped += 1
                continue

            # Dedup by source_hash
            if qd.get("source_hash"):
                existing = db.execute(
                    select(Question).where(Question.source_hash == qd["source_hash"])
                ).scalar_one_or_none()
                if existing:
                    skipped += 1
                    continue

            opts = qd.get("options")
            if opts and isinstance(opts, dict):
                opts_json = json.dumps(opts, ensure_ascii=False)
            else:
                opts_json = None

            tags = qd.get("tags", [])
            if isinstance(tags, list):
                tags_json = json.dumps(tags, ensure_ascii=False)
            else:
                tags_json = "[]"

            q = Question(
                exam_id=exam_id,
                question_no=qd["question_no"],
                question_type=qd["question_type"],
                stem=qd["stem"],
                options_json=opts_json,
                answer=qd.get("answer", ""),
                analysis=qd.get("analysis", ""),
                difficulty=qd.get("difficulty", 3),
                knowledge_area=qd.get("knowledge_area", ""),
                tags_json=tags_json,
                source_hash=qd.get("source_hash"),
                is_verified=qd.get("is_verified", False),
            )
            db.add(q)
            inserted += 1

        db.commit()
        print(f"Questions: inserted={inserted}, skipped={skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
