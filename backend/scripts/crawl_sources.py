import argparse
import json
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.source_service import html_to_text  # noqa: E402


LEGAL_NOTICE = "仅可采集自己整理、公开授权或合法取得的内容；不得绕过登录、付费墙、验证码或反爬限制。"


class LinkAndTitleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()


@dataclass
class RobotsCacheItem:
    parser: RobotFileParser
    loaded: bool


class SourceCrawler:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float,
        delay: float,
        max_chars: int,
        min_text_length: int,
        respect_robots: bool,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay = delay
        self.max_chars = max_chars
        self.min_text_length = min_text_length
        self.respect_robots = respect_robots
        self.robots_cache: dict[str, RobotsCacheItem] = {}

    def robots_allowed(self, client: httpx.Client, url: str) -> tuple[bool, str | None]:
        if not self.respect_robots:
            return True, None
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self.robots_cache.get(origin)
        if cached is None:
            robots_url = urljoin(origin, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                response = client.get(robots_url, headers={"User-Agent": self.user_agent})
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    cached = RobotsCacheItem(parser=parser, loaded=True)
                elif response.status_code in {401, 403}:
                    cached = RobotsCacheItem(parser=parser, loaded=False)
                    self.robots_cache[origin] = cached
                    return False, f"robots.txt 不允许读取：HTTP {response.status_code}"
                else:
                    cached = RobotsCacheItem(parser=parser, loaded=False)
            except httpx.HTTPError:
                cached = RobotsCacheItem(parser=parser, loaded=False)
            self.robots_cache[origin] = cached
        if not cached.loaded:
            return True, None
        allowed = cached.parser.can_fetch(self.user_agent, url)
        return allowed, None if allowed else "robots.txt 禁止当前 User-Agent 抓取"

    def fetch(self, client: httpx.Client, url: str) -> tuple[dict, list[str]]:
        allowed, blocked_reason = self.robots_allowed(client, url)
        if not allowed:
            return self.error_record(url, blocked_reason or "robots.txt 禁止抓取"), []

        try:
            response = client.get(url, headers={"User-Agent": self.user_agent})
        except httpx.HTTPError as exc:
            return self.error_record(url, f"请求失败：{exc}"), []

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if response.status_code >= 400:
            return self.error_record(url, f"HTTP {response.status_code}", response.status_code, content_type), []

        raw = response.text
        extractor = LinkAndTitleExtractor()
        links: list[str] = []
        if "html" in content_type or content_type in {"", "text/html", "application/xhtml+xml"}:
            extractor.feed(raw)
            text = html_to_text(raw)
            links = [normalize_url(urljoin(str(response.url), link)) for link in extractor.links]
        elif content_type.startswith("text/"):
            text = raw
        else:
            return self.error_record(url, f"暂不解析内容类型：{content_type}", response.status_code, content_type), []

        compact = compact_text(text)
        if len(compact) < self.min_text_length:
            return self.error_record(url, f"正文过短：{len(compact)} 字", response.status_code, content_type), links

        record = {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "title": extractor.title,
            "content": compact[: self.max_chars],
            "content_length": len(compact),
            "truncated": len(compact) > self.max_chars,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "legal_notice": LEGAL_NOTICE,
        }
        return record, links

    @staticmethod
    def error_record(
        url: str,
        error: str,
        status_code: int | None = None,
        content_type: str | None = None,
    ) -> dict:
        return {
            "url": url,
            "status_code": status_code,
            "content_type": content_type,
            "error": error,
            "content": "",
            "content_length": 0,
            "truncated": False,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "legal_notice": LEGAL_NOTICE,
        }


def compact_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_url(url: str) -> str:
    clean, _fragment = urldefrag(url)
    return clean.strip()


def same_domain(url: str, allowed_domains: set[str]) -> bool:
    return urlparse(url).netloc.lower() in allowed_domains


def load_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    urls.extend(args.url or [])
    if args.url_file:
        path = Path(args.url_file)
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)
    normalized = []
    seen: set[str] = set()
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            print(f"[crawl] 跳过非法 URL：{url}")
            continue
        clean = normalize_url(url)
        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="合规来源采集脚本：抓取用户明确提供的合法 URL 文本，不自动入库")
    parser.add_argument("--url", action="append", help="要采集的 URL，可重复传入")
    parser.add_argument("--url-file", help="URL 列表文件，UTF-8，一行一个 URL")
    parser.add_argument("--output", help="输出 JSONL 路径，默认写入 data/sources/")
    parser.add_argument("--max-pages", type=int, default=20, help="最多抓取页面数")
    parser.add_argument("--follow-links", action="store_true", help="跟随页面内同域名链接继续采集")
    parser.add_argument("--delay", type=float, default=1.5, help="请求间隔秒数")
    parser.add_argument("--timeout", type=float, default=20.0, help="请求超时秒数")
    parser.add_argument("--max-chars", type=int, default=60000, help="每页最多保存字符数")
    parser.add_argument("--min-text-length", type=int, default=80, help="正文少于该字符数则记录为失败")
    parser.add_argument("--user-agent", default="rk-network-engineer-bank/1.0", help="User-Agent")
    parser.add_argument("--confirm-legal", action="store_true", help="确认 URL 内容为自整理、公开授权或合法取得")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_legal:
        print(f"[crawl] 拒绝执行：请先确认合规来源。{LEGAL_NOTICE}")
        print("[crawl] 确认后追加参数：--confirm-legal")
        return 2

    urls = load_urls(args)
    if not urls:
        print("[crawl] 未提供有效 URL")
        return 1

    output = Path(args.output) if args.output else BACKEND_DIR / "data" / "sources" / f"crawl_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)

    allowed_domains = {urlparse(url).netloc.lower() for url in urls}
    queue: deque[str] = deque(urls)
    visited: set[str] = set()
    success = 0
    failed = 0

    crawler = SourceCrawler(
        user_agent=args.user_agent,
        timeout=args.timeout,
        delay=args.delay,
        max_chars=args.max_chars,
        min_text_length=args.min_text_length,
        respect_robots=True,
    )

    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client, output.open("w", encoding="utf-8") as fp:
        while queue and len(visited) < args.max_pages:
            url = queue.popleft()
            if url in visited:
                continue
            if not same_domain(url, allowed_domains):
                continue
            visited.add(url)
            print(f"[crawl] {len(visited)}/{args.max_pages} {url}")
            record, links = crawler.fetch(client, url)
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record.get("error"):
                failed += 1
                print(f"[crawl] 失败：{record['error']}")
            else:
                success += 1
                print(f"[crawl] 保存正文 {record['content_length']} 字")
            if args.follow_links:
                for link in links:
                    if link and link not in visited and same_domain(link, allowed_domains):
                        queue.append(link)
            time.sleep(max(0, args.delay))

    print(f"[crawl] 完成：success={success}, failed={failed}, output={output}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
