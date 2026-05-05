import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="统计题库质量问题，不修改数据库")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = db.execute(
            text(
                """
                select count(*) total,
                       sum(case when answer is not null and trim(answer) != '' then 1 else 0 end) with_answer,
                       sum(case when answer is null or trim(answer) = '' then 1 else 0 end) without_answer,
                       sum(case when question_type='single_choice' and (options_json is null or json_length(options_json)<2) then 1 else 0 end) bad_single_options
                from questions
                """
            )
        ).mappings().one()
        by_exam = db.execute(
            text(
                """
                select e.id exam_id,e.year,e.season,e.paper_type,count(q.id) total,
                       sum(case when q.answer is not null and trim(q.answer) != '' then 1 else 0 end) with_answer,
                       sum(case when q.answer is null or trim(q.answer) = '' then 1 else 0 end) without_answer,
                       round(sum(case when q.answer is not null and trim(q.answer) != '' then 1 else 0 end)/count(q.id), 4) answer_rate
                from exams e join questions q on q.exam_id=e.id
                group by e.id,e.year,e.season,e.paper_type
                order by answer_rate asc, total desc
                """
            )
        ).mappings().all()

    data = {
        "summary": {key: normalize(value) for key, value in dict(summary).items()},
        "by_exam": [{key: normalize(value) for key, value in dict(row).items()} for row in by_exam],
    }
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("summary:", data["summary"])
        for row in data["by_exam"]:
            print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
