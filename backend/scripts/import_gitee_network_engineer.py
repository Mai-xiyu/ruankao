import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
from pypdf import PdfReader


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = BACKEND_DIR / "data" / "sources" / "gitee_zaonai_network_engineer"
SOURCE_URL = "https://gitee.com/zaonai/network_engineer"
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class ExamTask:
    year: int
    season: str
    paper_type: str
    question_files: list[Path] = field(default_factory=list)
    answer_files: list[Path] = field(default_factory=list)

    @property
    def key(self) -> tuple[int, str, str]:
        return self.year, self.season, self.paper_type


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 zaonai/network_engineer Gitee 仓库抽取真题 PDF 并调用 DeepSeek 入库")
    parser.add_argument("--repo-dir", default=str(DEFAULT_REPO))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--years", default="2022-2024", help="年份列表或范围，例如 2011-2024 或 2022,2023")
    parser.add_argument("--seasons", default="上半年,下半年")
    parser.add_argument("--paper-types", default="上午综合知识,下午案例分析")
    parser.add_argument("--max-chars", type=int, default=60000)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--skip-existing-exams", action="store_true", help="如果该年份/上下半年/卷别已有题目，则跳过")
    parser.add_argument("--min-answer-rate", type=float, default=0.6, help="自动入库前要求有答案题目的最低比例")
    parser.add_argument("--min-questions", type=int, default=1, help="自动入库前要求的最低题目数")
    parser.add_argument("--use-reasoning-model", action="store_true")
    parser.add_argument("--output-dir", default=str(BACKEND_DIR / "data" / "gitee_imports"))
    parser.add_argument("--confirm-license", action="store_true", help="确认该仓库 LICENSE 允许处理这些材料")
    return parser.parse_args()


def parse_years(value: str) -> set[int]:
    years: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(item))
    return years


def detect_year_season(path: Path) -> tuple[int, str] | None:
    text = str(path)
    match = re.search(r"(20\d{2})年(上|下)半年", text)
    if not match:
        return None
    return int(match.group(1)), f"{match.group(2)}半年"


def detect_paper_type(path: Path) -> str | None:
    name = path.name
    if any(token in name for token in ("上午", "基础知识", "综合知识")):
        return "上午综合知识"
    if any(token in name for token in ("下午", "应用技术", "案例分析")):
        return "下午案例分析"
    return None


def is_answer_file(path: Path) -> bool:
    return any(token in path.name for token in ("答案", "解析", "详解"))


def find_license(repo_dir: Path) -> str:
    license_path = repo_dir / "LICENSE"
    if not license_path.exists():
        return ""
    return license_path.read_text(encoding="utf-8", errors="ignore")[:400]


def build_tasks(repo_dir: Path, years: set[int], seasons: set[str], paper_types: set[str]) -> list[ExamTask]:
    root = repo_dir / "02.历年真题（2005-2024年）+真题视频解析" / "2009-2024年历年真题及解析"
    task_map: dict[tuple[int, str, str], ExamTask] = {}
    for pdf in root.rglob("*.pdf"):
        detected = detect_year_season(pdf)
        if not detected:
            continue
        year, season = detected
        if year not in years or season not in seasons:
            continue
        paper_type = detect_paper_type(pdf)
        if paper_type and paper_type not in paper_types:
            continue

        if paper_type:
            task = task_map.setdefault((year, season, paper_type), ExamTask(year, season, paper_type))
            if is_answer_file(pdf):
                task.answer_files.append(pdf)
            else:
                task.question_files.append(pdf)
        elif is_answer_file(pdf):
            for target_paper_type in paper_types:
                task = task_map.setdefault((year, season, target_paper_type), ExamTask(year, season, target_paper_type))
                task.answer_files.append(pdf)

    return sorted(task_map.values(), key=lambda item: (item.year, item.season, item.paper_type), reverse=True)


def extract_pdf_text(path: Path, max_chars: int) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = [f"\n\n===== 文件：{path.name} =====\n"]
    used = 0
    for page_number, page in enumerate(reader.pages, start=1):
        if used >= max_chars:
            break
        text = page.extract_text() or ""
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not text:
            continue
        chunk = f"\n--- 第 {page_number} 页 ---\n{text}\n"
        remaining = max_chars - used
        parts.append(chunk[:remaining])
        used += len(chunk)
    return "\n".join(parts)


def build_task_text(task: ExamTask, max_chars: int) -> tuple[str, list[str]]:
    files = task.question_files + task.answer_files
    parts: list[str] = []
    used = 0
    used_files: list[str] = []
    for path in files:
        remaining = max_chars - used
        if remaining <= 0:
            break
        text = extract_pdf_text(path, remaining)
        if len(text.strip()) < 200:
            continue
        parts.append(text)
        used += len(text)
        used_files.append(str(path))
    return "\n".join(parts).strip(), used_files


def call_backend_json(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[bool, dict | str]:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        return False, f"后端请求失败：{exc}"
    if response.status_code >= 400:
        return False, f"HTTP {response.status_code}: {response.text[:1200]}"
    try:
        return True, response.json()
    except json.JSONDecodeError:
        return False, "后端返回不是 JSON"


def has_existing_questions(client: httpx.Client, base_url: str, task: ExamTask) -> bool:
    ok, result = call_backend_json(
        client,
        "GET",
        f"{base_url}/api/questions",
        params={
            "year": task.year,
            "season": task.season,
            "paper_type": task.paper_type,
            "has_answer": True,
            "limit": 1,
        },
    )
    return ok and isinstance(result, list) and len(result) > 0


def draft_quality(draft: dict) -> dict[str, int | float]:
    questions = draft.get("questions") or []
    total = len(questions)
    answered = 0
    single_without_options = 0
    for question in questions:
        if not isinstance(question, dict):
            continue
        answer = str(question.get("answer") or "").strip()
        if answer:
            answered += 1
        options = question.get("options") or {}
        if question.get("question_type") == "single_choice" and len(options) < 2:
            single_without_options += 1
    answer_rate = answered / total if total else 0
    return {
        "total": total,
        "answered": answered,
        "answer_rate": round(answer_rate, 4),
        "single_without_options": single_without_options,
    }


def is_quality_acceptable(quality: dict[str, int | float], min_answer_rate: float, min_questions: int) -> bool:
    if int(quality["total"]) < min_questions:
        return False
    if int(quality["single_without_options"]) > 0:
        return False
    return float(quality["answer_rate"]) >= min_answer_rate


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo_dir)
    if not args.confirm_license:
        print("[gitee-import] 拒绝执行：请追加 --confirm-license，确认仓库 LICENSE 允许处理这些材料")
        return 2
    if not repo_dir.exists():
        print(f"[gitee-import] 仓库目录不存在：{repo_dir}")
        return 1
    license_text = find_license(repo_dir)
    if "Apache License" not in license_text:
        print("[gitee-import] 未检测到 Apache License，停止")
        return 1

    years = parse_years(args.years)
    seasons = {item.strip() for item in args.seasons.split(",") if item.strip()}
    paper_types = {item.strip() for item in args.paper_types.split(",") if item.strip()}
    tasks = build_tasks(repo_dir, years, seasons, paper_types)
    if not tasks:
        print("[gitee-import] 没有匹配到可处理任务")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_log = output_dir / f"gitee_import_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    base_url = args.base_url.rstrip("/")
    imported = 0
    drafted = 0
    skipped = 0

    with httpx.Client(timeout=600) as client, run_log.open("w", encoding="utf-8") as fp:
        for index, task in enumerate(tasks, start=1):
            print(f"[gitee-import] {index}/{len(tasks)} {task.year} {task.season} {task.paper_type}")
            if args.skip_existing_exams and has_existing_questions(client, base_url, task):
                print("[gitee-import] 已有题目，跳过")
                skipped += 1
                fp.write(
                    json.dumps(
                        {
                            "year": task.year,
                            "season": task.season,
                            "paper_type": task.paper_type,
                            "files": [],
                            "text_length": 0,
                            "draft_path": None,
                            "import_result": None,
                            "decision": "skip_existing_exam",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                fp.flush()
                continue
            text, used_files = build_task_text(task, args.max_chars)
            item = {
                "year": task.year,
                "season": task.season,
                "paper_type": task.paper_type,
                "files": used_files,
                "text_length": len(text),
                "draft_path": None,
                "import_result": None,
                "decision": "pending",
            }
            if len(text) < 500:
                item["decision"] = "skip_text_too_short"
                skipped += 1
                fp.write(json.dumps(item, ensure_ascii=False) + "\n")
                fp.flush()
                continue

            exam = {
                "exam_name": "网络工程师",
                "level": "中级",
                "year": task.year,
                "season": task.season,
                "paper_type": task.paper_type,
                "source_name": "Gitee zaonai/network_engineer",
                "source_url": SOURCE_URL,
                "is_memory_version": False,
                "remark": "由 Apache-2.0 仓库 PDF 文本经 DeepSeek 结构化生成，需人工校对",
            }
            payload = {"text": text, "exam": exam, "use_reasoning_model": args.use_reasoning_model}
            ok, draft = call_backend_json(client, "POST", f"{base_url}/api/ai/extract-questions", json=payload)
            if not ok:
                item["decision"] = "extract_failed"
                item["error"] = draft
                skipped += 1
                fp.write(json.dumps(item, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"[gitee-import] 结构化失败：{draft}")
                time.sleep(max(0, args.delay))
                continue

            assert isinstance(draft, dict)
            draft_path = output_dir / f"draft_{task.year}_{task.season}_{task.paper_type}_{datetime.now():%H%M%S}.json"
            draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            item["draft_path"] = str(draft_path)
            item["draft_question_count"] = len(draft.get("questions", []))
            quality = draft_quality(draft)
            item["quality"] = quality
            drafted += 1

            if args.dry_run:
                item["decision"] = "drafted"
                fp.write(json.dumps(item, ensure_ascii=False) + "\n")
                fp.flush()
                time.sleep(max(0, args.delay))
                continue

            if not is_quality_acceptable(quality, args.min_answer_rate, args.min_questions):
                item["decision"] = "skip_quality_low"
                skipped += 1
                fp.write(json.dumps(item, ensure_ascii=False) + "\n")
                fp.flush()
                print(
                    "[gitee-import] 跳过低质量草稿："
                    f"total={quality['total']}, answered={quality['answered']}, "
                    f"answer_rate={quality['answer_rate']}"
                )
                time.sleep(max(0, args.delay))
                continue

            ok, import_result = call_backend_json(
                client,
                "POST",
                f"{base_url}/api/import/ai-json",
                params={"update_existing": args.update_existing},
                json=draft,
            )
            item["import_result"] = import_result
            if ok:
                item["decision"] = "imported"
                imported += 1
                print(f"[gitee-import] 入库完成：{item['draft_question_count']} 道草稿题")
            else:
                item["decision"] = "import_failed"
                skipped += 1
                print(f"[gitee-import] 入库失败：{import_result}")
            fp.write(json.dumps(item, ensure_ascii=False) + "\n")
            fp.flush()
            time.sleep(max(0, args.delay))

    print(f"[gitee-import] 完成：drafted={drafted}, imported={imported}, skipped={skipped}, log={run_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
