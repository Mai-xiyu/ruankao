import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.import_try_learning import BASE_URL, DATA_DIR, LEVEL_BY_CODE  # noqa: E402

QUESTION_KEYS = {"subject", "type", "typeExplain", "questionContent"}
STOP_WORDS = ("验证码", "付费", "购买", "充值", "会员", "密码")
SUBJECT_NAME_BY_CODE = {
    "xtghygls": "系统规划与管理师",
    "xtjgsjs": "系统架构设计师",
    "wlghsjs": "网络规划设计师",
    "xtfxs": "系统分析师",
    "xtjcxmglgcs": "系统集成项目管理工程师",
    "sjkxtgcs": "数据库系统工程师",
    "qrsxtsjs": "嵌入式系统设计师",
    "dmtyysjs": "多媒体应用设计师",
    "dzswsjs": "电子商务设计师",
    "xxaqgcs": "信息安全工程师",
    "rjsjs": "软件设计师",
    "wlgcs": "网络工程师",
    "rjpcs": "软件评测师",
    "xxcljsy": "信息处理技术员",
    "wlgly": "网络管理员",
    "cxy": "程序员",
}


def looks_like_question_rows(body: object) -> bool:
    if not isinstance(body, list) or not body:
        return False
    sample = body[0]
    return isinstance(sample, dict) and QUESTION_KEYS.issubset(sample.keys())


def code_from_url(url: str) -> str | None:
    name = Path(urlparse(url).path).stem
    if name in LEVEL_BY_CODE:
        return name
    return None


def code_from_subject_name(name: str | None) -> str | None:
    if not name:
        return None
    for code, subject_name in SUBJECT_NAME_BY_CODE.items():
        if subject_name == name:
            return code
    return None


def subject_name_for(code: str | None, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    if code:
        return SUBJECT_NAME_BY_CODE.get(code)
    return None


def capture_with_browser(
    *,
    candidate_no: str,
    duration: int,
    headless: bool,
    save_promoted: bool,
    subject_code: str | None = None,
    subject_name: str | None = None,
) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError(f"未安装 playwright，无法运行浏览器捕获：{exc}") from exc

    target_subject = subject_name_for(subject_code, subject_name)
    capture_dir = DATA_DIR / "browser_capture" / datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_dir.mkdir(parents=True, exist_ok=True)
    captured: list[dict] = []
    promoted: list[dict] = []

    def save_response(response) -> None:
        content_type = response.headers.get("content-type", "")
        url = response.url
        if "json" not in content_type.lower() and not url.lower().endswith(".json"):
            return
        try:
            body = response.json()
        except Exception:
            return

        index = len(captured) + 1
        filename = f"response_{index:03d}.json"
        path = capture_dir / filename
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

        code = code_from_url(url)
        if not code and looks_like_question_rows(body):
            code = code_from_subject_name(str(body[0].get("subject") or ""))

        item = {
            "url": url,
            "status": response.status,
            "file": str(path),
            "question_rows": looks_like_question_rows(body),
            "code": code,
        }
        captured.append(item)
        print(f"[capture] {response.status} {url} -> {path.name}")

        if save_promoted and item["question_rows"] and item["code"]:
            out_path = DATA_DIR / f"{item['code']}.json"
            out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
            promoted.append({"code": item["code"], "source": str(path), "target": str(out_path), "count": len(body)})
            print(f"[promote] {item['code']} -> {out_path.name} ({len(body)} rows)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.on("response", save_response)
        run_try_learning_flow(page, candidate_no=candidate_no, subject_name=target_subject)

        deadline = time.time() + max(duration, 3)
        while time.time() < deadline:
            page.wait_for_timeout(1_000)

        (capture_dir / "page.html").write_text(page.content(), encoding="utf-8")
        browser.close()

    manifest = capture_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"subject": target_subject, "captured": captured, "promoted": promoted}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"captured {len(captured)} JSON responses, manifest: {manifest}")
    return manifest


def run_try_learning_flow(page, *, candidate_no: str, subject_name: str | None) -> None:
    page.goto(f"{BASE_URL}/#/LoginView", wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(1_000)
    stop_if_sensitive(page)
    fill_candidate_no(page, candidate_no)
    click_any(page, ("登录", "进入", "确定", "确认", "下一步"))

    page.wait_for_url(re.compile(r".*#/SelectSubject.*"), timeout=30_000)
    page.wait_for_timeout(1_000)
    stop_if_sensitive(page)
    if subject_name:
        click_any(page, (subject_name,))
    else:
        click_any(page, tuple(SUBJECT_NAME_BY_CODE.values()))

    page.wait_for_url(re.compile(r".*#/MockPrinciple.*"), timeout=30_000)
    page.wait_for_timeout(1_000)
    stop_if_sensitive(page)
    click_any(page, ("阅读并同意遵守", "我已阅读", "同意", "确认", "开始"))

    page.wait_for_url(re.compile(r".*#/UserInfo.*"), timeout=30_000)
    page.wait_for_timeout(1_000)
    stop_if_sensitive(page)
    click_any(page, ("确认", "确定", "进入考试", "开始考试"))

    page.wait_for_timeout(3_000)


def stop_if_sensitive(page) -> None:
    html = page.content()
    if any(word in html for word in STOP_WORDS):
        raise RuntimeError("页面出现验证码/付费/密码等敏感流程提示，停止自动化。")


def fill_candidate_no(page, candidate_no: str) -> None:
    selectors = [
        "input[placeholder*='准考证']",
        "input[placeholder*='考号']",
        "input[placeholder*='账号']",
        "input[type='text']",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.fill(candidate_no, timeout=2_000)
                print(f"[fill] {selector} = {candidate_no}")
                return
        except Exception:
            continue
    raise RuntimeError("未找到准考证号输入框")


def click_any(page, texts: tuple[str, ...]) -> None:
    for text in texts:
        try:
            page.get_by_text(re.compile(re.escape(text))).first.click(timeout=3_000)
            print(f"[click] {text}")
            return
        except Exception:
            continue
    raise RuntimeError(f"未找到可点击文本：{', '.join(texts[:5])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="按 LoginView -> SelectSubject -> MockPrinciple -> UserInfo 捕获 try-learning XHR")
    parser.add_argument("--candidate-no", default="1234")
    parser.add_argument("--subject-code", choices=sorted(LEVEL_BY_CODE), help="科目代码，例如 wlgcs")
    parser.add_argument("--subject-name", help="科目名称，例如 网络工程师")
    parser.add_argument("--duration", type=int, default=20, help="进入考试后继续监听响应的秒数")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--promote", action="store_true", help="把识别出的题库 JSON 保存到 data/try_learning/{code}.json")
    parser.add_argument("--confirm-public-source", action="store_true")
    args = parser.parse_args()

    if not args.confirm_public_source:
        print("拒绝执行：请添加 --confirm-public-source，确认数据来源合法且不绕过登录、付费、验证码或反爬限制。")
        return 2
    try:
        capture_with_browser(
            candidate_no=args.candidate_no,
            duration=args.duration,
            headless=args.headless,
            save_promoted=args.promote,
            subject_code=args.subject_code,
            subject_name=args.subject_name,
        )
    except RuntimeError as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
