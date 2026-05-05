from html.parser import HTMLParser

import httpx
from fastapi import HTTPException, status


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


async def preview_source(text: str | None = None, url: str | None = None, limit: int = 12000) -> dict:
    if text:
        content = text
    elif url:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 http 或 https URL")
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "rk-network-engineer-bank/1.0"})
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"URL 读取失败，HTTP {response.status_code}")
        content_type = response.headers.get("content-type", "")
        raw = response.text
        content = html_to_text(raw) if "html" in content_type else raw
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text 或 url 必须提供一个")

    compact = "\n".join(line.strip() for line in content.splitlines() if line.strip())
    return {
        "content_excerpt": compact[:limit],
        "content_length": len(compact),
        "truncated": len(compact) > limit,
        "needs_confirmation": True,
        "compliance_notice": "仅可导入自己整理、公开授权或合法取得的数据；预览不会自动入库。",
    }

