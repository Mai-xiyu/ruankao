import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from crawl_sources import LEGAL_NOTICE, SourceCrawler, normalize_url  # noqa: E402


load_dotenv(BACKEND_DIR / ".env")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or "请在本地" in stripped or stripped.lower() in {"password", "changeme", "change-me"}


def default_queries(year: int, season: str, paper_type: str, exam_name: str) -> list[str]:
    paper_words = "上午 综合知识" if "上午" in paper_type else "下午 案例分析"
    return [
        f"软考 {exam_name} {year} {season} 真题 {paper_words}",
        f"{year}年{season} {exam_name} 真题 {paper_words}",
        f"{exam_name} {year} {season} 答案 解析 {paper_words}",
    ]


def search_searxng(query: str, max_results: int) -> list[SearchResult]:
    base_url = os.getenv("SEARXNG_BASE_URL", "").rstrip("/")
    if is_placeholder(base_url):
        raise RuntimeError("未配置 SEARXNG_BASE_URL，无法使用 SearXNG 搜索")
    response = httpx.get(
        f"{base_url}/search",
        params={"q": query, "format": "json", "language": "zh-CN", "safesearch": 1},
        headers={"User-Agent": "rk-network-engineer-bank/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    results: list[SearchResult] = []
    for item in data.get("results", [])[:max_results]:
        url = str(item.get("url") or "").strip()
        if url:
            results.append(
                SearchResult(
                    title=str(item.get("title") or ""),
                    url=normalize_url(url),
                    snippet=str(item.get("content") or ""),
                    provider="searxng",
                )
            )
    return results


def search_bing(query: str, max_results: int) -> list[SearchResult]:
    key = os.getenv("BING_SEARCH_API_KEY", "")
    endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
    if is_placeholder(key):
        raise RuntimeError("未配置 BING_SEARCH_API_KEY，无法使用 Bing Search API")
    response = httpx.get(
        endpoint,
        params={"q": query, "count": min(max_results, 50), "mkt": "zh-CN", "textDecorations": False},
        headers={"Ocp-Apim-Subscription-Key": key, "User-Agent": "rk-network-engineer-bank/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    results: list[SearchResult] = []
    for item in data.get("webPages", {}).get("value", [])[:max_results]:
        url = str(item.get("url") or "").strip()
        if url:
            results.append(
                SearchResult(
                    title=str(item.get("name") or ""),
                    url=normalize_url(url),
                    snippet=str(item.get("snippet") or ""),
                    provider="bing",
                )
            )
    return results


def run_search(provider: str, queries: list[str], max_results: int) -> list[SearchResult]:
    seen: set[str] = set()
    results: list[SearchResult] = []
    for query in queries:
        print(f"[pipeline] 搜索：{query}")
        if provider == "bing":
            batch = search_bing(query, max_results)
        elif provider == "searxng":
            batch = search_searxng(query, max_results)
        else:
            raise RuntimeError(f"不支持的搜索 provider：{provider}")
        for item in batch:
            if item.url not in seen and urlparse(item.url).scheme in {"http", "https"}:
                seen.add(item.url)
                results.append(item)
        time.sleep(0.8)
    return results[:max_results]


def domain_allowed(url: str, allow_domains: set[str]) -> bool:
    if not allow_domains:
        return False
    host = urlparse(url).netloc.lower()
    return host in allow_domains or any(host.endswith("." + domain) for domain in allow_domains)


def call_backend_json(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[bool, dict | str]:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        return False, f"后端请求失败：{exc}"
    if response.status_code >= 400:
        return False, f"HTTP {response.status_code}: {response.text[:1000]}"
    try:
        return True, response.json()
    except json.JSONDecodeError:
        return False, "后端返回不是 JSON"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="全网候选发现 -> 抓取 -> DeepSeek 审核 -> 结构化 -> 可选入库")
    parser.add_argument("--year", type=int, required=True, help="考试年份")
    parser.add_argument("--season", choices=["上半年", "下半年"], required=True, help="考试季节")
    parser.add_argument("--paper-type", default="上午综合知识", choices=["上午综合知识", "下午案例分析"], help="试卷类型")
    parser.add_argument("--exam-name", required=True, help="科目名称，例如 网络工程师、软件设计师")
    parser.add_argument("--level", required=True, choices=["高级", "中级", "初级"], help="科目级别")
    parser.add_argument("--query", action="append", help="自定义搜索词，可重复；不传则自动生成")
    parser.add_argument("--provider", choices=["searxng", "bing"], default=os.getenv("SEARCH_PROVIDER", "searxng"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--max-results", type=int, default=10, help="最多搜索候选数")
    parser.add_argument("--max-pages", type=int, default=10, help="最多抓取候选页数")
    parser.add_argument("--delay", type=float, default=2.0, help="抓取间隔秒数")
    parser.add_argument("--allow-domain", action="append", default=[], help="允许自动入库的域名，可重复")
    parser.add_argument("--auto-approve", action="store_true", help="允许低风险且可结构化的未知来源自动入库")
    parser.add_argument("--dry-run", action="store_true", help="只搜索、抓取和审核，不结构化入库")
    parser.add_argument("--use-reasoning-model", action="store_true", help="DeepSeek 审核/结构化使用推理模型")
    parser.add_argument("--update-existing", action="store_true", help="入库时更新重复题")
    parser.add_argument("--output", help="运行日志 JSONL，默认写入 data/web_pipeline/")
    parser.add_argument("--confirm-legal", action="store_true", help="确认仅处理合法来源候选")
    parser.add_argument("--session-cookie", help="管理员登录后的 rk_session cookie 值；仅在需要 HTTP 入库时使用")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_legal:
        print(f"[pipeline] 拒绝执行：{LEGAL_NOTICE}")
        print("[pipeline] 确认后追加参数：--confirm-legal")
        return 2

    queries = args.query or default_queries(args.year, args.season, args.paper_type, args.exam_name)
    output = Path(args.output) if args.output else BACKEND_DIR / "data" / "web_pipeline" / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    allow_domains = {domain.lower().strip() for domain in args.allow_domain if domain.strip()}
    exam = {
        "exam_name": args.exam_name,
        "level": args.level,
        "year": args.year,
        "season": args.season,
        "paper_type": args.paper_type,
        "source_name": "全网候选发现",
        "source_url": "",
        "is_memory_version": False,
        "remark": "全网候选发现后由 DeepSeek 结构化，需人工校对来源与内容",
    }

    try:
        results = run_search(args.provider, queries, args.max_results)
    except Exception as exc:
        print(f"[pipeline] 搜索失败：{exc}")
        return 1
    if not results:
        print("[pipeline] 没有搜索候选")
        return 1

    crawler = SourceCrawler(
        user_agent="rk-network-engineer-bank/1.0",
        timeout=25,
        delay=args.delay,
        max_chars=60000,
        min_text_length=120,
        respect_robots=True,
    )

    imported = 0
    drafted = 0
    skipped = 0
    base_url = args.base_url.rstrip("/")
    headers = {"Cookie": f"rk_session={args.session_cookie}"} if args.session_cookie else None

    with httpx.Client(timeout=120, follow_redirects=True, headers=headers) as client, output.open("w", encoding="utf-8") as fp:
        for index, result in enumerate(results[: args.max_pages], start=1):
            print(f"[pipeline] {index}/{min(len(results), args.max_pages)} 抓取：{result.url}")
            record, _links = crawler.fetch(client, result.url)
            run_item = {
                "search": result.__dict__,
                "fetch": {key: value for key, value in record.items() if key != "content"},
                "audit": None,
                "draft_question_count": 0,
                "import_result": None,
                "decision": "pending",
            }
            content = str(record.get("content") or "")
            if record.get("error") or not content:
                run_item["decision"] = "fetch_failed"
                skipped += 1
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                continue

            audit_payload = {
                "url": record.get("url", result.url),
                "title": record.get("title") or result.title,
                "content": content,
                "exam": exam,
                "year": args.year,
                "season": args.season,
                "paper_type": args.paper_type,
                "use_reasoning_model": args.use_reasoning_model,
            }
            ok, audit = call_backend_json(client, "POST", f"{base_url}/api/ai/audit-source", json=audit_payload)
            if not ok:
                run_item["decision"] = "audit_failed"
                run_item["audit"] = audit
                skipped += 1
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"[pipeline] 审核失败：{audit}")
                continue
            assert isinstance(audit, dict)
            run_item["audit"] = audit

            if not audit.get("relevant") or not audit.get("can_structure"):
                run_item["decision"] = "audit_rejected"
                skipped += 1
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"[pipeline] 跳过：{audit.get('reason')}")
                continue

            explicit_allowed = domain_allowed(str(record.get("url", result.url)), allow_domains)
            ai_auto_allowed = bool(audit.get("can_auto_import")) and audit.get("risk_level") == "low"
            can_import = explicit_allowed or args.auto_approve or ai_auto_allowed

            if args.dry_run:
                run_item["decision"] = "dry_run_audit_passed"
                drafted += 1
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                continue

            extract_payload = {"text": content, "exam": exam, "use_reasoning_model": args.use_reasoning_model}
            ok, draft = call_backend_json(client, "POST", f"{base_url}/api/ai/extract-questions", json=extract_payload)
            if not ok:
                run_item["decision"] = "extract_failed"
                run_item["draft_error"] = draft
                skipped += 1
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"[pipeline] 结构化失败：{draft}")
                continue
            assert isinstance(draft, dict)
            question_count = len(draft.get("questions", []))
            run_item["draft_question_count"] = question_count
            drafted += 1

            draft_path = output.parent / f"{output.stem}_draft_{index:03d}.json"
            draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            run_item["draft_path"] = str(draft_path)

            if not can_import:
                run_item["decision"] = "manual_review_required"
                fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
                fp.flush()
                print("[pipeline] 已生成草稿，等待人工确认或 allow-domain/auto-approve")
                continue

            ok, import_result = call_backend_json(
                client,
                "POST",
                f"{base_url}/api/import/ai-json",
                params={"update_existing": args.update_existing},
                json=draft,
            )
            if ok:
                run_item["decision"] = "imported"
                run_item["import_result"] = import_result
                imported += 1
                print(f"[pipeline] 已入库：{question_count} 道草稿题")
            else:
                run_item["decision"] = "import_failed"
                run_item["import_result"] = import_result
                skipped += 1
                print(f"[pipeline] 入库失败：{import_result}")
            fp.write(json.dumps(run_item, ensure_ascii=False) + "\n")
            fp.flush()
            time.sleep(max(0, args.delay))

    print(f"[pipeline] 完成：drafted={drafted}, imported={imported}, skipped={skipped}, log={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
