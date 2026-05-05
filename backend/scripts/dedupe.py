import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import Question  # noqa: E402
from app.utils.hash import question_hash  # noqa: E402


def main() -> int:
    buckets: dict[str, list[int]] = defaultdict(list)
    with SessionLocal() as db:
        questions = db.execute(select(Question)).scalars()
        for question in questions:
            buckets[question_hash(question.stem, question.options_json)].append(question.id)

    duplicates = {key: ids for key, ids in buckets.items() if len(ids) > 1}
    if not duplicates:
        print("[dedupe] 未发现重复题")
        return 0
    for digest, ids in duplicates.items():
        print(f"[dedupe] {digest}: {ids}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

