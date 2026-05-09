import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.schemas.importing import ImportPayload  # noqa: E402
from app.services.import_service import import_payload  # noqa: E402
from scripts.import_try_learning import DRAFT_DIR, build_payload, load_rows  # noqa: E402


def settings_or_fail():
    settings = get_settings()
    if not settings.deepseek_api_key.strip() or "请在本地" in settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    return settings


def call_deepseek(question: dict[str, Any], search_context: str | None, *, use_reasoning_model: bool) -> dict[str, Any]:
    settings = settings_or_fail()
    model = settings.deepseek_reasoning_model if use_reasoning_model else settings.deepseek_model
    system = (
        "你是软考题目答案校对助手。请基于题干、选项、图片说明和可选搜索摘要推断最可能答案。"
        "如果无法判断，answer 返回空字符串，confidence 返回 0。"
        "输出必须是合法 JSON：answer 字符串，analysis 字符串，confidence 0-1 数字。"
        "不要声称这是官方答案；只给可审查的推断。"
    )
    user = {
        "stem": question.get("stem"),
        "question_type": question.get("question_type"),
        "options": question.get("options"),
        "images": question.get("images", []),
        "search_context": search_context,
    }
    response = httpx.post(
        settings.deepseek_chat_url,
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:500]}")
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return json.loads(content)


def search_snippets(query: str, *, limit: int = 3) -> str | None:
    settings = get_settings()
    if settings.search_provider != "searxng" or not settings.searxng_base_url.strip():
        return None
    try:
        response = httpx.get(
            f"{settings.searxng_base_url.rstrip('/')}/search",
            params={"q": query[:500], "format": "json"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    snippets = []
    for item in data.get("results", [])[:limit]:
        title = item.get("title") or ""
        content = item.get("content") or ""
        url = item.get("url") or ""
        snippets.append(f"{title}\n{content}\n{url}".strip())
    return "\n\n".join(snippets) if snippets else None


def load_payload(args: argparse.Namespace) -> ImportPayload:
    if args.draft:
        data = json.loads(Path(args.draft).read_text(encoding="utf-8"))
        return ImportPayload.model_validate(data.get("payload", data))
    if not args.only:
        raise RuntimeError("请提供 --only 或 --draft")
    rows = load_rows(args.only)
    payload, _ = build_payload(args.only, rows, year=args.year, season=args.season)
    return payload


def enrich_payload(
    payload: ImportPayload,
    *,
    limit: int,
    min_confidence: float,
    use_search: bool,
    use_reasoning_model: bool,
    mark_ok: bool,
) -> tuple[ImportPayload, list[dict]]:
    logs: list[dict] = []
    processed = 0
    for question in payload.questions:
        if question.answer:
            continue
        if processed >= limit:
            break
        search_context = search_snippets(question.stem) if use_search else None
        raw = call_deepseek(question.model_dump(), search_context, use_reasoning_model=use_reasoning_model)
        answer = str(raw.get("answer") or "").strip()
        analysis = str(raw.get("analysis") or "").strip()
        try:
            confidence = float(raw.get("confidence") or 0)
        except ValueError:
            confidence = 0.0
        accepted = bool(answer) and confidence >= min_confidence
        if accepted:
            question.answer = answer
            question.analysis = analysis or question.analysis
            question.quality_status = "ok" if mark_ok else "ai_answered"
            question.is_verified = False
        logs.append(
            {
                "question_no": question.question_no,
                "accepted": accepted,
                "answer": answer,
                "confidence": confidence,
            }
        )
        processed += 1
        print(f"{question.question_no}: confidence={confidence:.2f} accepted={accepted} answer={answer}")
    return payload, logs


def main() -> int:
    parser = argparse.ArgumentParser(description="用 DeepSeek / 可选 SearXNG 给 try-learning 草稿推断答案")
    parser.add_argument("--only", help="科目代码，例如 wlgcs")
    parser.add_argument("--draft", help="已有草稿 JSON 路径")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--season", default="模拟")
    parser.add_argument("--limit", type=int, default=20, help="本次最多处理多少道无答案题")
    parser.add_argument("--min-confidence", type=float, default=0.75)
    parser.add_argument("--use-search", action="store_true", help="如果配置了 SEARXNG_BASE_URL，则检索摘要辅助判断")
    parser.add_argument("--use-reasoning-model", action="store_true")
    parser.add_argument("--mark-ok", action="store_true", help="高置信 AI 答案直接标记 quality_status=ok；默认标记 ai_answered")
    parser.add_argument("--import-to-db", action="store_true")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--confirm-ai-answers", action="store_true", help="确认接受 AI 推断答案为未校对草稿")
    args = parser.parse_args()

    if not args.confirm_ai_answers:
        print("拒绝执行：请添加 --confirm-ai-answers，确认 AI 答案只是未校对推断。")
        return 2

    payload = load_payload(args)
    payload, logs = enrich_payload(
        payload,
        limit=args.limit,
        min_confidence=args.min_confidence,
        use_search=args.use_search,
        use_reasoning_model=args.use_reasoning_model,
        mark_ok=args.mark_ok,
    )

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    name = args.only or Path(args.draft).stem
    out_path = DRAFT_DIR / f"{name}_ai_answers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps({"logs": logs, "payload": payload.model_dump()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {out_path}")

    if args.import_to_db:
        with SessionLocal() as db:
            result = import_payload(
                db,
                payload,
                source_file=str(out_path),
                source_type="try-learning-ai-answers",
                update_existing=args.update_existing,
                force_unverified=True,
            )
        print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
