import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.capture_try_learning_browser import looks_like_question_rows  # noqa: E402
from scripts.import_try_learning import DATA_DIR, LEVEL_BY_CODE  # noqa: E402


def code_from_payload(path: Path, rows: list[dict]) -> str | None:
    code = Path(urlparse(path.stem).path).stem
    if code in LEVEL_BY_CODE:
        return code
    subject = str(rows[0].get("subject") or "").strip() if rows else ""
    for candidate in LEVEL_BY_CODE:
        if candidate in path.name:
            return candidate
    subject_to_code = {
        "系统规划与管理师": "xtghygls",
        "系统架构设计师": "xtjgsjs",
        "网络规划设计师": "wlghsjs",
        "系统分析师": "xtfxs",
        "系统集成项目管理工程师": "xtjcxmglgcs",
        "数据库系统工程师": "sjkxtgcs",
        "嵌入式系统设计师": "qrsxtsjs",
        "多媒体应用设计师": "dmtyysjs",
        "电子商务设计师": "dzswsjs",
        "信息安全工程师": "xxaqgcs",
        "软件设计师": "rjsjs",
        "网络工程师": "wlgcs",
        "软件评测师": "rjpcs",
        "信息处理技术员": "xxcljsy",
        "网络管理员": "wlgly",
        "程序员": "cxy",
    }
    return subject_to_code.get(subject)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 browser_capture 中识别 try-learning 题库响应并提升为标准 JSON 文件")
    parser.add_argument("--capture-dir", type=Path, default=DATA_DIR / "browser_capture")
    parser.add_argument("--confirm-public-source", action="store_true")
    args = parser.parse_args()

    if not args.confirm_public_source:
        print("拒绝执行：请添加 --confirm-public-source，确认数据来源合法。")
        return 2
    if not args.capture_dir.exists():
        print(f"捕获目录不存在：{args.capture_dir}")
        return 1

    promoted = []
    for path in sorted(args.capture_dir.rglob("response_*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not looks_like_question_rows(body):
            continue
        code = code_from_payload(path, body)
        if not code:
            print(f"[skip] 无法识别科目代码：{path}")
            continue
        target = DATA_DIR / f"{code}.json"
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        promoted.append({"code": code, "source": str(path), "target": str(target), "count": len(body)})
        print(f"[promote] {code}: {len(body)} rows -> {target}")

    report = DATA_DIR / "browser_capture" / "promote_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(promoted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"promoted={len(promoted)}, report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
