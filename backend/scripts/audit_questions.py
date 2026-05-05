"""
题目质量审查脚本

使用 DeepSeek AI 批量审查数据库中的题目，标记有问题的题目。

用法:
    python scripts/audit_questions.py --dry-run     # 只输出问题列表
    python scripts/audit_questions.py --fix          # 自动修复可修复的问题
    python scripts/audit_questions.py --batch-size 20  # 每批审查20题
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Question, Exam  # noqa: E402
from sqlalchemy import select, func  # noqa: E402


def log(msg: str):
    print(f"[audit] {msg}", flush=True)


AUDIT_PROMPT = """你是软考网络工程师题库质量审查员。请审查以下题目，判断每道题是否有问题。

审查标准：
1. stem 题干是否完整、通顺、有意义
2. 选择题必须有 A/B/C/D 四个选项（或多选题有更多）
3. 填空题的空位是否明确
4. 答案是否正确（如果能判断）
5. 题干是否包含无关内容（水印、广告、题号引用错误等）
6. 选项内容是否合理（不应出现"选项A"这种占位符）

输入格式：JSON 数组，每个元素包含 id, question_no, question_type, stem, options, answer

输出 JSON：
{
  "results": [
    {
      "id": 123,
      "status": "ok" | "bad" | "fixable",
      "issue": "问题描述（status为ok时留空）",
      "fix": {"field": "new_value"} // 仅 status=fixable 时提供
    }
  ]
}

status 含义：
- ok: 题目质量合格
- bad: 有严重问题，建议删除
- fixable: 有问题但可以自动修复"""


async def audit_batch(questions: list[dict], settings) -> list[dict]:
    """用 DeepSeek 审查一批题目。"""
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": AUDIT_PROMPT},
            {"role": "user", "content": json.dumps(questions, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(settings.deepseek_chat_url, headers=headers, json=payload)

    if resp.status_code >= 400:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    result = json.loads(content)
    return result.get("results", [])


def question_to_dict(q) -> dict:
    """将 Question ORM 对象转为审查用 dict。"""
    opts = {}
    if q.options_json:
        try:
            opts = json.loads(q.options_json) if isinstance(q.options_json, str) else q.options_json
        except:
            opts = {}
    return {
        "id": q.id,
        "question_no": q.question_no,
        "question_type": q.question_type,
        "stem": q.stem[:500] if q.stem else "",
        "options": opts,
        "answer": q.answer or "",
    }


async def main_async(args):
    settings = get_settings()

    if not settings.deepseek_api_key or "请在本地" in settings.deepseek_api_key:
        log("错误: 未配置 DEEPSEEK_API_KEY")
        return 1

    with SessionLocal() as db:
        # Get all questions
        query = select(Question).order_by(Question.id)
        if args.exam_id:
            query = query.where(Question.exam_id == args.exam_id)

        questions = db.execute(query).scalars().all()
        log(f"待审查: {len(questions)} 道题")

        # Convert to dicts
        q_dicts = [question_to_dict(q) for q in questions]

        # Skip ones that look fine (case analysis fill-in-blank questions are special)
        # Focus on single_choice and multiple_choice
        reviewable = [q for q in q_dicts if q["question_type"] in ("single_choice", "multiple_choice")]
        skip_count = len(q_dicts) - len(reviewable)
        log(f"跳过非选择题（案例/填空/配置）: {skip_count} 道")
        log(f"需要审查的选择题: {len(reviewable)} 道")

    # Batch review
    batch_size = args.batch_size
    all_results = []
    errors = 0

    for i in range(0, len(reviewable), batch_size):
        batch = reviewable[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(reviewable) + batch_size - 1) // batch_size
        log(f"审查批次 {batch_num}/{total_batches} ({len(batch)} 题)...")

        try:
            results = await audit_batch(batch, settings)
            all_results.extend(results)
            ok = sum(1 for r in results if r.get("status") == "ok")
            bad = sum(1 for r in results if r.get("status") == "bad")
            fix = sum(1 for r in results if r.get("status") == "fixable")
            log(f"  结果: ok={ok}, bad={bad}, fixable={fix}")
        except Exception as e:
            log(f"  错误: {e}")
            errors += 1

        # Rate limit
        await asyncio.sleep(1)

    # Summary
    log("")
    log("=" * 50)
    ok = sum(1 for r in all_results if r.get("status") == "ok")
    bad = sum(1 for r in all_results if r.get("status") == "bad")
    fixable = sum(1 for r in all_results if r.get("status") == "fixable")
    log(f"审查完成: {len(all_results)} 道题")
    log(f"  合格: {ok}")
    log(f"  需修复: {fixable}")
    log(f"  需删除: {bad}")

    # Output bad and fixable
    if bad > 0:
        log("\n--- 建议删除 ---")
        for r in all_results:
            if r.get("status") == "bad":
                log(f"  ID={r['id']}: {r.get('issue', '')}")

    if fixable > 0:
        log("\n--- 可修复 ---")
        for r in all_results:
            if r.get("status") == "fixable":
                log(f"  ID={r['id']}: {r.get('issue', '')}")
                if r.get("fix"):
                    log(f"    Fix: {r['fix']}")

    # Apply fixes if requested
    if args.fix and (bad > 0 or fixable > 0):
        log("\n--- 应用修复 ---")
        with SessionLocal() as db:
            # Delete bad questions
            bad_ids = [r["id"] for r in all_results if r.get("status") == "bad"]
            if bad_ids:
                from sqlalchemy import delete
                result = db.execute(delete(Question).where(Question.id.in_(bad_ids)))
                log(f"删除了 {result.rowcount} 道问题题目")

            # Apply fixes
            fix_count = 0
            for r in all_results:
                if r.get("status") == "fixable" and r.get("fix"):
                    q = db.get(Question, r["id"])
                    if q:
                        for field, value in r["fix"].items():
                            if field == "stem":
                                q.stem = value
                            elif field == "answer":
                                q.answer = value
                            elif field == "options":
                                q.options_json = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value
                            elif field == "question_type":
                                q.question_type = value
                        fix_count += 1
            db.commit()
            log(f"修复了 {fix_count} 道题")

    # Save report
    report_path = BACKEND_DIR / "data" / "audit_report.json"
    report_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\n审查报告已保存: {report_path}")

    return 0 if errors == 0 else 1


def parse_args():
    parser = argparse.ArgumentParser(description="题目质量审查")
    parser.add_argument("--dry-run", action="store_true", default=True, help="只输出问题（默认）")
    parser.add_argument("--fix", action="store_true", help="自动修复问题")
    parser.add_argument("--batch-size", type=int, default=15, help="每批审查题数")
    parser.add_argument("--exam-id", type=int, default=None, help="只审查指定试卷")
    return parser.parse_args()


def main():
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
