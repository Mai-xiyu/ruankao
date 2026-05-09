import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


LEGAL_NOTICE = "仅可处理自己整理、公开授权或合法取得的内容；AI 草稿默认未人工校对。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把采集 JSONL 交给后端 DeepSeek v4 接口生成题目 JSON 草稿")
    parser.add_argument("source_jsonl", help="crawl_sources.py 输出的 JSONL")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--output", help="输出草稿 JSON，默认写入 data/ai_drafts/")
    parser.add_argument("--exam-name", required=True, help="科目名称，例如 网络工程师、软件设计师")
    parser.add_argument("--level", required=True, choices=["高级", "中级", "初级"], help="科目级别")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--season", default="上半年")
    parser.add_argument("--paper-type", default="上午综合知识")
    parser.add_argument("--source-name", default="合规采集")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--max-chars", type=int, default=60000)
    parser.add_argument("--use-reasoning-model", action="store_true")
    parser.add_argument("--import-to-db", action="store_true", help="草稿生成后直接调用 /api/import/ai-json 入库")
    parser.add_argument("--update-existing", action="store_true", help="入库时更新重复题")
    parser.add_argument("--confirm-legal", action="store_true", help="确认来源合法")
    parser.add_argument("--session-cookie", help="管理员登录后的 rk_session cookie 值；仅在 --import-to-db 时需要")
    return parser.parse_args()


def read_source_text(path: Path, max_chars: int) -> tuple[str, list[str]]:
    chunks: list[str] = []
    urls: list[str] = []
    used = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        content = str(record.get("content") or "").strip()
        if not content:
            continue
        url = str(record.get("url") or "").strip()
        if url:
            urls.append(url)
        header = f"\n\n来源：{url}\n"
        remaining = max_chars - used
        if remaining <= 0:
            break
        piece = (header + content)[:remaining]
        chunks.append(piece)
        used += len(piece)
    return "\n".join(chunks).strip(), urls


def main() -> int:
    args = parse_args()
    if not args.confirm_legal:
        print(f"[ai-extract] 拒绝执行：请先确认合规来源。{LEGAL_NOTICE}")
        print("[ai-extract] 确认后追加参数：--confirm-legal")
        return 2

    source_path = Path(args.source_jsonl)
    if not source_path.exists():
        print(f"[ai-extract] 文件不存在：{source_path}")
        return 1

    text, urls = read_source_text(source_path, args.max_chars)
    if not text:
        print("[ai-extract] 没有可用正文")
        return 1

    source_url = args.source_url or (urls[0] if urls else "")
    payload = {
        "text": text,
        "exam": {
            "exam_name": args.exam_name,
            "level": args.level,
            "year": args.year,
            "season": args.season,
            "paper_type": args.paper_type,
            "source_name": args.source_name,
            "source_url": source_url,
            "is_memory_version": False,
            "remark": "由合规来源采集文本生成的 AI 草稿，需人工校对",
        },
        "use_reasoning_model": args.use_reasoning_model,
    }

    base_url = args.base_url.rstrip("/")
    headers = {"Cookie": f"rk_session={args.session_cookie}"} if args.session_cookie else None
    try:
        with httpx.Client(timeout=120, headers=headers) as client:
            response = client.post(f"{base_url}/api/ai/extract-questions", json=payload)
            if response.status_code >= 400:
                print(f"[ai-extract] AI 结构化失败：HTTP {response.status_code} {response.text}")
                return 1
            draft = response.json()
            output = Path(args.output) if args.output else BACKEND_DIR / "data" / "ai_drafts" / f"draft_{datetime.now():%Y%m%d_%H%M%S}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[ai-extract] 草稿已写入：{output}")

            if args.import_to_db:
                import_response = client.post(
                    f"{base_url}/api/import/ai-json",
                    params={"update_existing": args.update_existing},
                    json=draft,
                )
                if import_response.status_code >= 400:
                    print(f"[ai-extract] 入库失败：HTTP {import_response.status_code} {import_response.text}")
                    return 1
                print("[ai-extract] 入库结果：")
                print(json.dumps(import_response.json(), ensure_ascii=False, indent=2))
    except httpx.HTTPError as exc:
        print(f"[ai-extract] 后端请求失败：{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
