import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.schemas.importing import ImportPayload  # noqa: E402
from app.services.import_service import get_or_create_subject, import_payload  # noqa: E402
from app.utils.hash import question_hash  # noqa: E402

BASE_URL = "https://www.try-learning.com"
DATA_DIR = BACKEND_DIR / "data" / "try_learning"
DRAFT_DIR = DATA_DIR / "drafts"
IMAGE_DIR = DATA_DIR / "images"

LEVEL_BY_CODE = {
    "xtghygls": "高级",
    "xtjgsjs": "高级",
    "wlghsjs": "高级",
    "xtfxs": "高级",
    "xtjcxmglgcs": "中级",
    "sjkxtgcs": "中级",
    "qrsxtsjs": "中级",
    "dmtyysjs": "中级",
    "dzswsjs": "中级",
    "xxaqgcs": "中级",
    "rjsjs": "中级",
    "wlgcs": "中级",
    "rjpcs": "中级",
    "xxcljsy": "初级",
    "wlgly": "初级",
    "cxy": "初级",
}

IMAGE_WORDS = ("图", "表", "拓扑", "日志", "波形", "如下图", "截图")
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
TAG_RE = re.compile(r"<[^>]+>")


def clean_html(text: str | None) -> str:
    value = (text or "").replace("&nbsp;", " ").replace("\u00a0", " ")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = TAG_RE.sub("", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip().strip('"')


def html_image_urls(text: str | None) -> list[str]:
    return IMG_RE.findall(text or "")


def row_image_urls(row: dict) -> list[str]:
    urls: list[str] = []
    for key in ("questionContent", "question", "questionA", "questionB", "questionC", "questionD"):
        urls.extend(html_image_urls(str(row.get(key) or "")))
    return list(dict.fromkeys(urls))


def image_items(row: dict, image_map: dict[str, str] | None = None) -> list[dict]:
    image_map = image_map or {}
    items: list[dict] = []
    for url in html_image_urls(str(row.get("questionContent") or "")) + html_image_urls(str(row.get("question") or "")):
        items.append({"image_path": image_map.get(url, url), "image_type": "stem", "caption": "题干图片"})
    for letter in "ABCD":
        for url in html_image_urls(str(row.get(f"question{letter}") or "")):
            items.append({"image_path": image_map.get(url, url), "image_type": f"option_{letter}", "caption": f"选项 {letter} 图片"})
    return items


def requires_image(row: dict, stem: str) -> bool:
    return bool(row_image_urls(row) or any(word in stem for word in IMAGE_WORDS))


def map_question_type(raw_type: str | None) -> str:
    text_value = (raw_type or "").strip()
    if "单" in text_value and "选" in text_value:
        return "single_choice"
    if "多" in text_value and "选" in text_value:
        return "multiple_choice"
    if "案例" in text_value:
        return "case_study"
    if "论文" in text_value:
        return "essay"
    return "other"


def infer_subject_name(code: str, rows: list[dict]) -> str:
    for row in rows:
        subject = str(row.get("subject") or "").strip()
        if subject:
            return subject
    return code


def infer_paper_type(rows: list[dict]) -> str:
    labels = Counter(str(row.get("typeExplain") or "").strip() for row in rows if row.get("typeExplain"))
    if not labels:
        return "模拟考试"
    return labels.most_common(1)[0][0] or "模拟考试"


def extract_answer(row: dict) -> str | None:
    for key in ("answer", "questionAnswer", "rightAnswer", "standardAnswer", "correctAnswer"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def extract_analysis(row: dict) -> str | None:
    for key in ("analysis", "questionAnalysis", "explain", "solution", "answerAnalysis"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return clean_html(str(value))
    return None


def convert_row(code: str, row: dict, index: int, image_map: dict[str, str] | None = None) -> dict | None:
    stem = clean_html(row.get("questionContent"))
    sub_questions = clean_html(row.get("question"))
    if sub_questions:
        stem = f"{stem}\n\n{sub_questions}".strip()
    if not stem:
        return None

    images = image_items(row, image_map=image_map)
    options = {}
    for letter in "ABCD":
        raw = str(row.get(f"question{letter}") or "")
        value = clean_html(raw)
        if value:
            options[letter] = value
        elif html_image_urls(raw):
            options[letter] = "图片选项"

    answer = extract_answer(row)
    needs_image = requires_image(row, stem)
    qtype = map_question_type(row.get("type"))
    quality = "ok"
    if not answer:
        quality = "missing_answer"
    elif qtype == "single_choice" and len(options) < 2:
        quality = "bad_options"
    elif needs_image and not images:
        quality = "missing_image"

    subject_name = str(row.get("subject") or "").strip()
    return {
        "question_no": str(index + 1),
        "question_type": qtype,
        "stem": stem,
        "options": options or None,
        "answer": answer,
        "analysis": extract_analysis(row),
        "difficulty": 3,
        "knowledge_area": subject_name or None,
        "tags": [subject_name] if subject_name else [],
        "source_provider": "try-learning",
        "source_question_id": f"{code}:{index + 1}",
        "source_url": f"{BASE_URL}/{code}.json",
        "quality_status": quality,
        "requires_image": needs_image,
        "is_verified": False,
        "images": images,
    }


def load_rows(code: str) -> list[dict]:
    path = DATA_DIR / f"{code}.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到 {path}，请先运行 scripts/crawl_try_learning.py")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_payload(
    code: str,
    rows: list[dict],
    *,
    year: int,
    season: str,
    image_map: dict[str, str] | None = None,
) -> tuple[ImportPayload, dict]:
    subject_name = infer_subject_name(code, rows)
    level = LEVEL_BY_CODE.get(code, "中级")
    questions = [item for index, row in enumerate(rows) if (item := convert_row(code, row, index, image_map=image_map))]
    hashes = [question_hash(item["stem"], item.get("options")) for item in questions]
    duplicate_count = len(hashes) - len(set(hashes))
    answer_count = sum(1 for item in questions if item.get("answer"))
    option_ready_count = sum(
        1 for item in questions if item["question_type"] != "single_choice" or (item.get("options") and len(item["options"]) >= 2)
    )
    image_required_count = sum(1 for item in questions if item["requires_image"])
    image_ready_count = sum(1 for item in questions if not item["requires_image"] or item.get("images"))
    image_count = sum(len(item.get("images") or []) for item in questions)
    report = {
        "code": code,
        "subject": subject_name,
        "level": level,
        "raw_count": len(rows),
        "converted_count": len(questions),
        "answer_rate": round(answer_count / max(len(questions), 1), 4),
        "option_ready_rate": round(option_ready_count / max(len(questions), 1), 4),
        "image_required_count": image_required_count,
        "image_ready_rate": round(image_ready_count / max(len(questions), 1), 4),
        "image_count": image_count,
        "duplicate_count": duplicate_count,
        "quality_status": Counter(item["quality_status"] for item in questions),
    }
    payload = ImportPayload.model_validate(
        {
            "exam": {
                "exam_name": subject_name,
                "level": level,
                "year": year,
                "season": season,
                "paper_type": infer_paper_type(rows),
                "source_name": "try-learning.com",
                "source_url": f"{BASE_URL}/{code}.json",
                "is_memory_version": False,
                "remark": "try-learning 公开模拟考试数据源转换草稿；入库前需通过质量门槛。",
            },
            "questions": questions,
        }
    )
    return payload, report


def passes_quality_gate(report: dict, *, allow_unanswered: bool) -> bool:
    if allow_unanswered:
        return (
            report["converted_count"] > 0
            and report["option_ready_rate"] >= 0.95
            and report["image_ready_rate"] >= 0.98
            and report["duplicate_count"] < report["converted_count"]
        )
    return (
        report["converted_count"] > 0
        and report["answer_rate"] >= 0.95
        and report["option_ready_rate"] >= 0.95
        and report["image_ready_rate"] >= 0.98
        and report["duplicate_count"] < report["converted_count"]
    )


def save_draft(code: str, payload: ImportPayload, report: dict) -> Path:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFT_DIR / f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(
        json.dumps({"report": report, "payload": payload.model_dump()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def download_images(code: str, rows: list[dict]) -> dict[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, str] = {}
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for url in sorted({url for row in rows for url in row_image_urls(row)}):
            parsed = urlparse(url)
            suffix = Path(parsed.path).suffix or ".png"
            filename = f"{code}_{question_hash(url)[:16]}{suffix}"
            path = IMAGE_DIR / filename
            if not path.exists():
                resp = client.get(url)
                resp.raise_for_status()
                path.write_bytes(resp.content)
            downloaded[url] = f"/static/data/try_learning/images/{filename}"
    return downloaded


def import_code(code: str, *, year: int, season: str, update_existing: bool, allow_unanswered: bool, download_image_files: bool) -> dict:
    rows = load_rows(code)
    image_map = download_images(code, rows) if download_image_files else {}
    payload, report = build_payload(code, rows, year=year, season=season, image_map=image_map)
    with SessionLocal() as db:
        get_or_create_subject(db, level=report["level"], name=report["subject"])
        db.commit()
    if not passes_quality_gate(report, allow_unanswered=allow_unanswered):
        draft = save_draft(code, payload, report)
        report["draft_file"] = str(draft)
        report["imported"] = False
        return report

    with SessionLocal() as db:
        result = import_payload(
            db,
            payload,
            source_file=f"try-learning:{code}",
            source_type="try-learning",
            update_existing=update_existing,
            force_unverified=True,
        )
    report["imported"] = True
    report["import_result"] = result.model_dump()
    return report


def candidate_codes(args: argparse.Namespace) -> list[str]:
    if args.only:
        return [args.only]
    if args.all_subjects:
        return sorted(code for code in LEVEL_BY_CODE if (DATA_DIR / f"{code}.json").exists())
    return sorted(path.stem for path in DATA_DIR.glob("*.json") if path.stem in LEVEL_BY_CODE)


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 try-learning 公开模拟考试 JSON 响应")
    parser.add_argument("--candidate-no", default="1234", help="静态 JSON 导入不会使用；浏览器抓取时保留")
    parser.add_argument("--all-subjects", action="store_true", help="导入 data/try_learning 中所有已知科目")
    parser.add_argument("--only", help="只处理指定科目代码，例如 wlgcs")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--season", default="模拟")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--allow-unanswered", action="store_true", help="允许无答案题以非 ok 状态入库；默认只保存草稿不入库")
    parser.add_argument("--download-images", action="store_true", help="下载题干和选项中的公开图片")
    parser.add_argument("--confirm-public-source", action="store_true", help="确认只处理公开、授权或合法取得的数据源")
    args = parser.parse_args()

    if not args.confirm_public_source:
        print("拒绝执行：请添加 --confirm-public-source，确认数据来源合法且不绕过登录、付费、验证码或反爬限制。")
        return 2
    if args.only and args.only not in LEVEL_BY_CODE:
        print(f"未知科目代码：{args.only}")
        return 2

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    reports = [
        import_code(
            code,
            year=args.year,
            season=args.season,
            update_existing=args.update_existing,
            allow_unanswered=args.allow_unanswered,
            download_image_files=args.download_images,
        )
        for code in candidate_codes(args)
    ]
    out_path = DRAFT_DIR / f"try_learning_import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for report in reports:
        print(
            f"{report['level']} | {report['subject']}: converted={report['converted_count']} "
            f"answer_rate={report['answer_rate']} images={report['image_count']} imported={report['imported']}"
        )
        if report.get("draft_file"):
            print(f"  draft: {report['draft_file']}")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
