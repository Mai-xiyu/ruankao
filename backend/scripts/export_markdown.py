import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import Question  # noqa: E402


def main() -> int:
    output = BACKEND_DIR / "data" / "exports" / "questions.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        questions = db.execute(select(Question).options(joinedload(Question.exam)).order_by(Question.id)).scalars()
        parts: list[str] = ["# 题库导出\n"]
        for question in questions:
            exam = question.exam
            parts.append(f"## {exam.year} {exam.season} {exam.paper_type} - {question.question_no}\n")
            parts.append(f"**类型**：{question.question_type}\n\n")
            parts.append(f"**题干**：\n\n{question.stem}\n\n")
            if question.options_json:
                parts.append("**选项**：\n\n")
                for key, value in question.options_json.items():
                    parts.append(f"- {key}. {value}\n")
                parts.append("\n")
            parts.append(f"**答案**：{question.answer or ''}\n\n")
            parts.append(f"**解析**：\n\n{question.analysis or ''}\n\n")
            parts.append(f"**知识点**：{question.knowledge_area or ''}\n\n")
            parts.append(f"**标签**：{', '.join(question.tags_json or [])}\n\n")
    output.write_text("\n".join(parts), encoding="utf-8")
    print(f"[export] 已导出：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

