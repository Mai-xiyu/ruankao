"""
PDF 真题批量提取脚本

从 PDF 文件中提取软考真题，通过 DeepSeek AI 结构化后导入多科目题库。

用法:
    python scripts/extract_pdf_questions.py --dry-run              # 只输出 JSON，不入库
    python scripts/extract_pdf_questions.py --year 2023 --dry-run  # 只处理 2023 年
    python scripts/extract_pdf_questions.py --import               # 提取后直接导入数据库
    python scripts/extract_pdf_questions.py --year 2023 --import   # 组合使用
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from pypdf import PdfReader

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.services.import_service import import_payload, load_import_payload  # noqa: E402
from app.database import SessionLocal  # noqa: E402

SOURCES_DIR = BACKEND_DIR / "data" / "sources" / "gitee_zaonai_network_engineer"
OUTPUT_DIR = BACKEND_DIR / "data" / "pdf_extracted"
EXAM_SUBDIR = "02.历年真题（2005-2024年）+真题视频解析"
YEAR_SUBDIR = "2009-2024年历年真题及解析"

# 需要从 PDF 文本中清除的水印模式
WATERMARK_PATTERNS = [
    r"软考达人[：:].*?(?:\n|$)",
    r"手机端题库[：:].*?(?:\n|$)",
    r"PC端题库[：:].*?(?:\n|$)",
    r"www\.ruankaodaren\.com.*?(?:\n|$)",
    r"微信搜索.*?(?:\n|$)",
    r"免费提供\d+w\+.*?(?:\n|$)",
    r"\d+TB免费.*?(?:\n|$)",
    r"专业备考平台.*?(?:\n|$)",
    r"专业备考资料.*?(?:\n|$)",
]
WATERMARK_RE = re.compile("|".join(WATERMARK_PATTERNS), re.MULTILINE)

CHUNK_SIZE = 12000  # 每个 chunk 的最大字符数


def log(msg: str) -> None:
    print(f"[pdf-extract] {msg}", flush=True)


# ──────────────────────────────────────────────
# 1. 扫描 PDF 文件
# ──────────────────────────────────────────────

def parse_filename(filename: str) -> dict | None:
    """从文件名解析 year, season, paper_type。"""
    name = Path(filename).stem

    # 跳过答案详解
    if "答案详解" in name or "答案" in name and "解析" in name and "真题" not in name:
        return None

    # 解析年份
    year_match = re.search(r"(20\d{2})", name)
    if not year_match:
        return None
    year = int(year_match.group(1))

    # 解析季节
    if "上半年" in name or "5月" in name or "春季" in name:
        season = "上半年"
    elif "下半年" in name or "11月" in name or "秋季" in name:
        season = "下半年"
    else:
        # 尝试从目录名解析
        return None

    # 解析试卷类型
    if "基础知识" in name or "综合知识" in name or "上午" in name:
        paper_type = "上午综合知识"
    elif "应用技术" in name or "案例分析" in name or "下午" in name:
        paper_type = "下午案例分析"
    else:
        return None

    return {"year": year, "season": season, "paper_type": paper_type}


def scan_pdfs(year_filter: int | None = None) -> list[dict]:
    """扫描所有 PDF 文件，返回 [{path, year, season, paper_type}]。"""
    exam_dir = SOURCES_DIR / EXAM_SUBDIR / YEAR_SUBDIR
    if not exam_dir.exists():
        log(f"目录不存在: {exam_dir}")
        return []

    results = []
    for pdf_path in sorted(exam_dir.rglob("*.pdf")):
        info = parse_filename(pdf_path.name)
        if not info:
            continue
        if year_filter and info["year"] != year_filter:
            continue
        info["path"] = str(pdf_path)
        results.append(info)

    log(f"找到 {len(results)} 个试卷 PDF" + (f"（{year_filter} 年）" if year_filter else ""))
    return results


# ──────────────────────────────────────────────
# 2. PDF 文本提取
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """清理水印和无关文字。"""
    text = WATERMARK_RE.sub("", text)
    # 去除多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(pdf_path: str) -> str:
    """提取 PDF 全文文本。"""
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    full_text = "\n\n".join(pages)
    return clean_text(full_text)


def chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """将长文本按段落边界切分为多个 chunk。"""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    # 按题目编号分割（1、2、3、... 或 1. 2. 3. ...）
    lines = text.split("\n")
    for line in lines:
        if len(current) + len(line) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current.strip())

    return chunks


# ──────────────────────────────────────────────
# 3. DeepSeek AI 结构化
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是软考多科目真题提取助手。用户会给你从考试 PDF 中提取的文本，请把其中的题目结构化为 JSON。

规则：
1. 只提取真实存在的题目，不要编造或补全题目
2. 复合题（如 23-24、25-26）拆成独立的题目，question_no 分别为 "23"、"24"
3. 去除水印、广告、页码等无关文字
4. 选择题 options 必须是 {"A":"...","B":"...","C":"...","D":"..."} 格式
5. 如果题目有明确答案，填入 answer 字段；如果没有，留空
6. difficulty 默认填 3，后续可以用 AI 建议
7. 自动推断 knowledge_area（知识点领域）和 tags（标签数组）
8. question_type: 单选 single_choice，多选 multiple_choice，填空 fill_blank，案例 case，配置 config，计算 calculation
9. question_no 必须是字符串
10. 所有 is_verified 必须为 false

输出必须是合法 JSON 对象：
{
  "questions": [
    {
      "question_no": "1",
      "question_type": "single_choice",
      "stem": "题干内容",
      "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
      "answer": "B",
      "analysis": "",
      "difficulty": 3,
      "knowledge_area": "网络基础",
      "tags": ["OSI模型", "TCP/IP"],
      "is_verified": false
    }
  ]
}"""


async def call_deepseek(
    text: str,
    exam_hint: dict,
    settings,
    use_reasoning: bool = False,
) -> list[dict]:
    """调用 DeepSeek API 提取题目。"""
    model = settings.deepseek_reasoning_model if use_reasoning else settings.deepseek_model
    user_payload = {
        "exam_hint": exam_hint,
        "content": text,
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(settings.deepseek_chat_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(f"DeepSeek API 错误 {response.status_code}: {response.text[:500]}")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    result = json.loads(content)
    return result.get("questions", [])


async def extract_questions_from_pdf(
    pdf_path: str,
    exam_hint: dict,
    settings,
    use_reasoning: bool = False,
) -> list[dict]:
    """从单个 PDF 提取所有题目。"""
    log(f"  提取文本: {Path(pdf_path).name}")
    full_text = extract_pdf_text(pdf_path)
    if not full_text:
        log(f"  警告: PDF 文本为空")
        return []

    chunks = chunk_text(full_text)
    log(f"  文本长度 {len(full_text)} 字，分为 {len(chunks)} 个 chunk")

    all_questions = []
    for i, chunk in enumerate(chunks):
        log(f"  处理 chunk {i+1}/{len(chunks)} ({len(chunk)} 字)...")
        try:
            questions = await call_deepseek(chunk, exam_hint, settings, use_reasoning)
            all_questions.extend(questions)
            log(f"    提取到 {len(questions)} 道题")
        except Exception as exc:
            log(f"    错误: {exc}")

    return all_questions


# ──────────────────────────────────────────────
# 4. 答案匹配
# ──────────────────────────────────────────────

def find_answer_pdf(exam_pdf_path: str) -> str | None:
    """在同目录下查找对应的答案详解 PDF。"""
    pdf_dir = Path(exam_pdf_path).parent
    for f in pdf_dir.iterdir():
        if f.suffix.lower() == ".pdf" and ("答案" in f.name or "解析" in f.name):
            return str(f)
    return None


async def extract_answers_from_pdf(
    answer_pdf_path: str,
    settings,
) -> dict[str, str]:
    """从答案 PDF 提取 question_no → answer 映射。"""
    log(f"  提取答案: {Path(answer_pdf_path).name}")
    full_text = extract_pdf_text(answer_pdf_path)
    if not full_text:
        return {}

    # 截断到 60000 字
    if len(full_text) > 60000:
        full_text = full_text[:60000]

    system = """从以下文本中提取题号和答案的对应关系。
输出 JSON: {"answers": {"1": "B", "2": "A", ...}}
题号为字符串，答案为选项字母（如 A/B/C/D）或填空答案。
只提取能明确对应的内容。"""

    user_payload = {"content": full_text}
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(settings.deepseek_chat_url, headers=headers, json=payload)

    if response.status_code >= 400:
        log(f"  答案提取失败: {response.status_code}")
        return {}

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    result = json.loads(content)
    answers = result.get("answers", {})
    log(f"  提取到 {len(answers)} 个答案")
    return answers


# ──────────────────────────────────────────────
# 5. 合并 & 输出
# ──────────────────────────────────────────────

def merge_questions(chunks_questions: list[list[dict]]) -> list[dict]:
    """合并多个 chunk 的题目，按 question_no 去重。"""
    seen = {}
    for questions in chunks_questions:
        for q in questions:
            qno = str(q.get("question_no", "")).strip()
            if qno and qno not in seen:
                seen[qno] = q
    # 按题号排序
    def sort_key(item):
        nums = re.findall(r"\d+", item[0])
        return tuple(int(n) for n in nums) if nums else (9999,)
    return [q for _, q in sorted(seen.items(), key=sort_key)]


def apply_answers(questions: list[dict], answers: dict[str, str]) -> int:
    """将答案合并到题目中。返回匹配数量。"""
    matched = 0
    for q in questions:
        qno = str(q.get("question_no", "")).strip()
        if qno in answers and not q.get("answer"):
            q["answer"] = answers[qno]
            matched += 1
    return matched


def build_import_payload(questions: list[dict], exam_info: dict, exam_name: str, level: str) -> dict:
    """构建 ImportPayload 格式的 JSON。"""
    return {
        "exam": {
            "exam_name": exam_name,
            "level": level,
            "year": exam_info["year"],
            "season": exam_info["season"],
            "paper_type": exam_info["paper_type"],
            "source_name": f"PDF 提取 - {exam_info['year']}年{exam_info['season']}",
            "source_url": "",
            "is_memory_version": False,
            "remark": f"从 PDF 真题自动提取，未经人工校对",
        },
        "questions": questions,
    }


def save_json(payload: dict, exam_info: dict) -> Path:
    """保存 JSON 文件。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{exam_info['year']}_{exam_info['season']}_{exam_info['paper_type']}.json"
    filename = filename.replace("/", "_").replace(" ", "_")
    out_path = OUTPUT_DIR / filename
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ──────────────────────────────────────────────
# 6. 主流程
# ──────────────────────────────────────────────

async def process_one(
    exam_info: dict,
    settings,
    do_import: bool,
    use_reasoning: bool,
    exam_name: str,
    level: str,
) -> dict:
    """处理单个试卷 PDF。"""
    pdf_path = exam_info["path"]
    label = f"{exam_info['year']}年{exam_info['season']} {exam_info['paper_type']}"
    log(f"处理: {label}")

    # 提取题目
    questions = await extract_questions_from_pdf(pdf_path, exam_info, settings, use_reasoning)
    if not questions:
        log(f"  未提取到题目，跳过")
        return {"label": label, "questions": 0, "imported": False}

    # 尝试匹配答案
    answer_pdf = find_answer_pdf(pdf_path)
    if answer_pdf:
        try:
            answers = await extract_answers_from_pdf(answer_pdf, settings)
            matched = apply_answers(questions, answers)
            log(f"  答案匹配: {matched}/{len(questions)}")
        except Exception as exc:
            log(f"  答案提取失败: {exc}")

    # 标记所有题目为未校对
    for q in questions:
        q["is_verified"] = False

    # 构建 import payload
    payload = build_import_payload(questions, exam_info, exam_name, level)

    # 保存 JSON
    out_path = save_json(payload, exam_info)
    log(f"  已保存: {out_path} ({len(questions)} 道题)")

    # 导入数据库
    imported = False
    if do_import:
        try:
            import_payload_data = load_import_payload(out_path)
            with SessionLocal() as db:
                result = import_payload(
                    db,
                    import_payload_data,
                    source_file=str(out_path),
                    source_type="pdf-extract",
                    update_existing=False,
                    force_unverified=True,
                )
            log(f"  导入完成: 新增 {result.success_count}, 跳过 {result.skipped_count}, 失败 {result.failed_count}")
            imported = True
        except Exception as exc:
            log(f"  导入失败: {exc}")

    return {"label": label, "questions": len(questions), "imported": imported}


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()

    # 检查 API key
    if not settings.deepseek_api_key or "请在本地" in settings.deepseek_api_key:
        log("错误: 未配置 DEEPSEEK_API_KEY，请在 .env 中填写")
        return 1

    # 扫描 PDF
    pdfs = scan_pdfs(args.year)
    if not pdfs:
        log("未找到匹配的 PDF 文件")
        return 1

    do_import = args.import_db
    use_reasoning = args.reasoning

    log(f"模式: {'导入数据库' if do_import else '仅输出 JSON'}")
    log(f"模型: {'推理模型' if use_reasoning else '标准模型'}")
    log("")

    total_questions = 0
    total_imported = 0
    errors = 0

    for exam_info in pdfs:
        try:
            result = await process_one(exam_info, settings, do_import, use_reasoning, args.exam_name, args.level)
            total_questions += result["questions"]
            if result["imported"]:
                total_imported += 1
        except Exception as exc:
            log(f"  处理失败: {exc}")
            errors += 1
        log("")

    log("=" * 50)
    log(f"处理完成: {len(pdfs)} 个试卷, {total_questions} 道题, {errors} 个错误")
    if do_import:
        log(f"已导入: {total_imported} 个试卷")

    return 0 if errors == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 PDF 真题中提取题目并导入题库")
    parser.add_argument("--exam-name", required=True, help="入库科目名称")
    parser.add_argument("--level", required=True, choices=["高级", "中级", "初级"], help="入库科目级别")
    parser.add_argument("--year", type=int, default=None, help="只处理指定年份（如 2023）")
    parser.add_argument("--dry-run", action="store_true", help="只输出 JSON，不导入数据库（默认）")
    parser.add_argument("--import", dest="import_db", action="store_true", help="提取后直接导入数据库")
    parser.add_argument("--reasoning", action="store_true", help="使用推理模型（更慢但更准确）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # 默认 dry-run
    if not args.import_db:
        args.dry_run = True
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
