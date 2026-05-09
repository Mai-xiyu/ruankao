import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.capture_try_learning_browser import capture_with_browser  # noqa: E402
from scripts.crawl_try_learning import download_one  # noqa: E402
from scripts.import_try_learning import DATA_DIR, DRAFT_DIR, LEVEL_BY_CODE, import_code  # noqa: E402


def download_static(codes: list[str]) -> list[str]:
    downloaded: list[str] = []
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, headers={"User-Agent": "rk-bank-importer/0.3"}) as client:
        for code in codes:
            data = download_one(client, code)
            if not data:
                continue
            (DATA_DIR / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            downloaded.append(code)
    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description="软考通/try-learning 合规自动抓取、识别、质量门槛导入流水线")
    parser.add_argument("--candidate-no", default="1234")
    parser.add_argument("--only", help="只处理指定科目代码，例如 wlgcs")
    parser.add_argument("--all-subjects", action="store_true")
    parser.add_argument("--browser", action="store_true", help="额外运行浏览器公开流程捕获 XHR")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--season", default="模拟")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--allow-unanswered", action="store_true", help="允许无答案题入库；默认只保存草稿")
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--confirm-public-source", action="store_true")
    args = parser.parse_args()

    if not args.confirm_public_source:
        print("拒绝执行：请添加 --confirm-public-source，确认数据来源合法且不绕过登录、付费、验证码或反爬限制。")
        return 2
    if args.only and args.only not in LEVEL_BY_CODE:
        print(f"未知科目代码：{args.only}")
        return 2

    codes = [args.only] if args.only else sorted(LEVEL_BY_CODE)
    if args.browser:
        try:
            capture_with_browser(
                candidate_no=args.candidate_no,
                duration=args.duration,
                headless=args.headless,
                save_promoted=True,
                subject_code=args.only,
                subject_name=None,
            )
        except RuntimeError as exc:
            print(f"[browser-skip] {exc}")

    downloaded = download_static(codes)
    reports = []
    for code in sorted(set(downloaded) | {path.stem for path in DATA_DIR.glob("*.json") if path.stem in codes}):
        reports.append(
            import_code(
                code,
                year=args.year,
                season=args.season,
                update_existing=args.update_existing,
                allow_unanswered=args.allow_unanswered,
                download_image_files=args.download_images,
            )
        )

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DRAFT_DIR / f"try_learning_pipeline_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for report in reports:
        print(
            f"{report['level']} | {report['subject']}: converted={report['converted_count']} "
            f"answer_rate={report['answer_rate']} images={report.get('image_count', 0)} imported={report['imported']}"
        )
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
