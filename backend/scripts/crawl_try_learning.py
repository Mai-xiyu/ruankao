import argparse
import json
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.import_try_learning import BASE_URL, DATA_DIR, LEVEL_BY_CODE  # noqa: E402


def download_one(client: httpx.Client, code: str) -> list[dict] | None:
    url = f"{BASE_URL}/{code}.json"
    try:
        resp = client.get(url, timeout=30)
        if resp.status_code == 404:
            print(f"[404] {code}.json")
            return None
        resp.raise_for_status()
        data = json.loads(resp.text.lstrip("\ufeff"))
        if not isinstance(data, list):
            print(f"[skip] {code}.json: response is not a list")
            return None
        print(f"[ok] {code}.json: {len(data)} rows")
        return data
    except Exception as exc:
        print(f"[err] {code}.json: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 try-learning 公开模拟考试 JSON 响应")
    parser.add_argument("--only", help="只下载指定科目代码，例如 wlgcs")
    parser.add_argument("--all-subjects", action="store_true", help="下载全部已知科目")
    parser.add_argument("--import", dest="do_import", action="store_true", help="下载后执行质量门槛导入")
    parser.add_argument("--candidate-no", default="1234")
    parser.add_argument("--confirm-public-source", action="store_true", help="确认只处理公开、授权或合法取得的数据源")
    args = parser.parse_args()

    if not args.confirm_public_source:
        print("拒绝执行：请添加 --confirm-public-source，确认数据来源合法且不绕过登录、付费、验证码或反爬限制。")
        return 2
    if args.only and args.only not in LEVEL_BY_CODE:
        print(f"未知科目代码：{args.only}")
        return 2

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    codes = [args.only] if args.only else sorted(LEVEL_BY_CODE)
    if not args.all_subjects and not args.only:
        codes = sorted(LEVEL_BY_CODE)

    downloaded: list[str] = []
    with httpx.Client(follow_redirects=True, headers={"User-Agent": "rk-bank-importer/0.3"}) as client:
        for code in codes:
            data = download_one(client, code)
            if not data:
                continue
            (DATA_DIR / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            downloaded.append(code)

    print(f"downloaded: {len(downloaded)}/{len(codes)}")
    if args.do_import and downloaded:
        from scripts.import_try_learning import import_code

        for code in downloaded:
            report = import_code(
                code,
                year=2026,
                season="模拟",
                update_existing=False,
                allow_unanswered=False,
                download_image_files=False,
            )
            print(f"import {code}: imported={report['imported']} answer_rate={report['answer_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
