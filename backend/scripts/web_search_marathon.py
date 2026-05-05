import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PIPELINE = BACKEND_DIR / "scripts" / "web_search_pipeline.py"


def parse_years(value: str) -> list[int]:
    years: list[int] = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            years.extend(range(int(start), int(end) + 1))
        else:
            years.append(int(item))
    return sorted(set(years), reverse=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="长时间循环执行全网候选一条龙脚本")
    parser.add_argument("--years", default="2024", help="年份列表或范围，例如 2020-2024 或 2022,2023,2024")
    parser.add_argument("--seasons", default="上半年,下半年", help="季节列表，逗号分隔")
    parser.add_argument("--paper-types", default="上午综合知识,下午案例分析", help="试卷类型列表，逗号分隔")
    parser.add_argument("--duration-hours", type=float, default=10.0, help="运行时长")
    parser.add_argument("--provider", choices=["searxng", "bing"], default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--cycle-sleep", type=float, default=30.0, help="每轮任务之间暂停秒数")
    parser.add_argument("--allow-domain", action="append", default=[])
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-reasoning-model", action="store_true")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--confirm-legal", action="store_true")
    return parser.parse_args()


def build_command(args: argparse.Namespace, year: int, season: str, paper_type: str) -> list[str]:
    cmd = [
        sys.executable,
        str(PIPELINE),
        "--year",
        str(year),
        "--season",
        season,
        "--paper-type",
        paper_type,
        "--base-url",
        args.base_url,
        "--max-results",
        str(args.max_results),
        "--max-pages",
        str(args.max_pages),
        "--delay",
        str(args.delay),
    ]
    if args.provider:
        cmd.extend(["--provider", args.provider])
    for domain in args.allow_domain:
        cmd.extend(["--allow-domain", domain])
    for flag in ("auto_approve", "dry_run", "use_reasoning_model", "update_existing", "confirm_legal"):
        if getattr(args, flag):
            cmd.append("--" + flag.replace("_", "-"))
    return cmd


def main() -> int:
    args = parse_args()
    if not args.confirm_legal:
        print("[marathon] 拒绝执行：请追加 --confirm-legal，确认仅处理合法来源候选")
        return 2

    years = parse_years(args.years)
    seasons = [item.strip() for item in args.seasons.split(",") if item.strip()]
    paper_types = [item.strip() for item in args.paper_types.split(",") if item.strip()]
    tasks = [(year, season, paper_type) for year in years for season in seasons for paper_type in paper_types]
    if not tasks:
        print("[marathon] 没有可执行任务")
        return 1

    deadline = datetime.now() + timedelta(hours=args.duration_hours)
    run_index = 0
    print(f"[marathon] start={datetime.now().isoformat(timespec='seconds')} deadline={deadline.isoformat(timespec='seconds')}")
    while datetime.now() < deadline:
        year, season, paper_type = tasks[run_index % len(tasks)]
        run_index += 1
        print(f"[marathon] round={run_index} year={year} season={season} paper_type={paper_type}")
        cmd = build_command(args, year, season, paper_type)
        completed = subprocess.run(cmd, cwd=BACKEND_DIR, check=False)
        print(f"[marathon] round={run_index} exit_code={completed.returncode}")
        remaining = (deadline - datetime.now()).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(args.cycle_sleep, remaining))
    print(f"[marathon] done rounds={run_index} end={datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

