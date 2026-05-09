import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.services.import_service import import_payload, load_import_payload  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入软考多科目题库 JSON")
    parser.add_argument("json_file", help="JSON 文件路径")
    parser.add_argument("--update-existing", action="store_true", help="更新重复题的答案、解析、标签和难度")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.json_file)
    if not path.exists():
        print(f"[import] 文件不存在：{path}")
        return 1

    try:
        payload = load_import_payload(path)
        with SessionLocal() as db:
            result = import_payload(
                db,
                payload,
                source_file=str(path),
                source_type="json",
                update_existing=args.update_existing,
            )
        print(f"[import] batch_id={result.batch_id}")
        print(
            "[import] "
            f"total={result.total_count}, success={result.success_count}, "
            f"updated={result.updated_count}, skipped={result.skipped_count}, failed={result.failed_count}"
        )
        for error in result.errors:
            print(f"[import] {error}")
        return 0 if result.failed_count == 0 else 1
    except Exception as exc:
        print(f"[import] 导入失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
