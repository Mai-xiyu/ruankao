"""
扫描版 PDF OCR 提取脚本

对 pypdf 无法提取文字的扫描版 PDF，使用 OCR 识别文字后再用 DeepSeek 结构化。

用法:
    python scripts/ocr_extract.py --dry-run              # 只输出 JSON
    python scripts/ocr_extract.py --import               # 提取后导入数据库
    python scripts/ocr_extract.py --year 2023 --import   # 只处理 2023 年
    python scripts/ocr_extract.py --method local         # 使用本地 PaddleOCR
"""

import argparse
import asyncio
import base64
import json
import re
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.services.import_service import import_payload, load_import_payload  # noqa: E402
from app.database import SessionLocal  # noqa: E402

SOURCES_DIR = BACKEND_DIR / "data" / "sources" / "gitee_zaonai_network_engineer"
OUTPUT_DIR = BACKEND_DIR / "data" / "pdf_extracted"
EXAM_SUBDIR = "02.历年真题（2005-2024年）+真题视频解析"
YEAR_SUBDIR = "2009-2024年历年真题及解析"

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

CHUNK_SIZE = 12000


def log(msg: str) -> None:
    print(f"[ocr-extract] {msg}", flush=True)


# ──────────────────────────────────────────────
# 1. 扫描需要 OCR 的 PDF（pypdf 提取不到文字的）
# ──────────────────────────────────────────────

def is_scanned_pdf(pdf_path: str) -> bool:
    """判断是否为扫描版 PDF（大部分页面没有可提取的文字）。"""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    if len(reader.pages) == 0:
        return False
    empty_pages = 0
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if len(text) < 20:
            empty_pages += 1
    return empty_pages / len(reader.pages) > 0.5


def scan_scanned_pdfs(year_filter: int | None = None) -> list[dict]:
    """扫描所有 PDF，找出需要 OCR 的。"""
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
        # 检查是否为扫描版
        try:
            if is_scanned_pdf(str(pdf_path)):
                info["path"] = str(pdf_path)
                results.append(info)
                log(f"  扫描版: {pdf_path.name}")
        except Exception as e:
            log(f"  检查失败: {pdf_path.name} - {e}")

    log(f"找到 {len(results)} 个扫描版 PDF" + (f"（{year_filter} 年）" if year_filter else ""))
    return results


def parse_filename(filename: str) -> dict | None:
    """从文件名解析 year, season, paper_type。"""
    name = Path(filename).stem
    if "答案详解" in name or ("答案" in name and "解析" in name and "真题" not in name):
        return None
    year_match = re.search(r"(20\d{2})", name)
    if not year_match:
        return None
    year = int(year_match.group(1))
    if "上半年" in name or "5月" in name or "春季" in name:
        season = "上半年"
    elif "下半年" in name or "11月" in name or "秋季" in name:
        season = "下半年"
    else:
        return None
    if "基础知识" in name or "综合知识" in name or "上午" in name:
        paper_type = "上午综合知识"
    elif "应用技术" in name or "案例分析" in name or "下午" in name:
        paper_type = "下午案例分析"
    else:
        return None
    return {"year": year, "season": season, "paper_type": paper_type}


# ──────────────────────────────────────────────
# 2. PDF 页面渲染为图片
# ──────────────────────────────────────────────

def render_pdf_pages(pdf_path: str, dpi: int = 200) -> list[bytes]:
    """将 PDF 每页渲染为 PNG 图片，返回图片字节列表。"""
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # 渲染为图片（dpi 越高越清晰，但 API 有大小限制）
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append(img_bytes)
    doc.close()
    return images


# ──────────────────────────────────────────────
# 3. 在线 OCR（ocr.space 免费 API）
# ──────────────────────────────────────────────

OCR_SPACE_URL = "https://api.ocr.space/parse/image"


async def ocr_space_single(image_bytes: bytes, api_key: str, lang: str = "chs") -> str:
    """调用 ocr.space 识别单张图片。"""
    b64 = base64.b64encode(image_bytes).decode()
    data = {
        "base64Image": f"data:image/png;base64,{b64}",
        "language": lang,
        "isOverlayRequired": "false",
        "OCREngine": "2",  # Engine 2 对中文更好
        "scale": "true",
    }
    headers = {"apikey": api_key}

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OCR_SPACE_URL, data=data, headers=headers)

    if resp.status_code >= 400:
        raise RuntimeError(f"ocr.space API error {resp.status_code}: {resp.text[:300]}")

    result = resp.json()
    if result.get("IsErroredOnProcessing"):
        raise RuntimeError(f"ocr.space error: {result.get('ErrorMessage', 'unknown')}")

    texts = []
    for parsed in result.get("ParsedResults", []):
        texts.append(parsed.get("ParsedText", ""))
    return "\n".join(texts)


async def ocr_with_ocr_space(pdf_path: str, api_key: str) -> str:
    """使用 ocr.space 对整个 PDF 进行 OCR。"""
    images = render_pdf_pages(pdf_path, dpi=200)
    log(f"  渲染了 {len(images)} 页")

    all_text = []
    for i, img_bytes in enumerate(images):
        # 跳过过大的图片（ocr.space 免费版限制 1MB）
        if len(img_bytes) > 1024 * 1024:
            log(f"    页面 {i+1}: 图片过大 ({len(img_bytes)//1024}KB)，降低 DPI 重试")
            doc = fitz.open(pdf_path)
            page = doc.load_page(i)
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            doc.close()

        log(f"    OCR 页面 {i+1}/{len(images)} ({len(img_bytes)//1024}KB)...")
        try:
            text = await ocr_space_single(img_bytes, api_key)
            all_text.append(text)
        except Exception as e:
            log(f"    页面 {i+1} OCR 失败: {e}")

    return "\n\n".join(all_text)


# ──────────────────────────────────────────────
# 4. 本地 OCR（PaddleOCR）
# ──────────────────────────────────────────────

def ocr_with_paddle(pdf_path: str) -> str:
    """使用 PaddleOCR 对 PDF 进行本地 OCR。"""
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise RuntimeError("PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle")

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    images = render_pdf_pages(pdf_path, dpi=200)
    log(f"  渲染了 {len(images)} 页")

    all_text = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, img_bytes in enumerate(images):
            tmp_path = Path(tmpdir) / f"page_{i}.png"
            tmp_path.write_bytes(img_bytes)
            log(f"    OCR 页面 {i+1}/{len(images)}...")
            result = ocr.ocr(str(tmp_path), cls=True)
            page_text = []
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]  # (bbox, (text, confidence))
                    page_text.append(text)
            all_text.append("\n".join(page_text))

    return "\n\n".join(all_text)


# ──────────────────────────────────────────────
# 5. DeepSeek AI 结构化（复用 extract_pdf_questions 的 prompt）
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是软考中级网络工程师真题提取助手。用户会给你从考试 PDF 中通过 OCR 识别的文字，请把其中的题目结构化为 JSON。

规则：
1. 只提取真实存在的题目，不要编造或补全题目
2. 复合题（如 23-24、25-26）拆成独立的题目，question_no 分别为 "23"、"24"
3. 去除水印、广告、页码等无关文字
4. OCR 可能有识别错误，请根据上下文修正明显的 OCR 错误（如 "l" 和 "1"、"O" 和 "0"）
5. 选择题 options 必须是 {"A":"...","B":"...","C":"...","D":"..."} 格式
6. 如果题目有明确答案，填入 answer 字段；如果没有，留空
7. difficulty 默认填 3
8. 自动推断 knowledge_area 和 tags
9. question_type: 单选 single_choice，多选 multiple_choice，填空 fill_blank，案例 case，配置 config，计算 calculation
10. question_no 必须是字符串
11. 所有 is_verified 必须为 false

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


async def call_deepseek(text: str, exam_hint: dict, settings) -> list[dict]:
    """调用 DeepSeek API 提取题目。"""
    model = settings.deepseek_model
    user_payload = {"exam_hint": exam_hint, "content": text}
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
        raise RuntimeError(f"DeepSeek API error {response.status_code}: {response.text[:500]}")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    result = json.loads(content)
    return result.get("questions", [])


def chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def clean_text(text: str) -> str:
    text = WATERMARK_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ──────────────────────────────────────────────
# 6. 主流程
# ──────────────────────────────────────────────

async def process_one(exam_info: dict, settings, do_import: bool, method: str) -> dict:
    pdf_path = exam_info["path"]
    label = f"{exam_info['year']}年{exam_info['season']} {exam_info['paper_type']}"
    log(f"处理: {label}")

    # OCR 提取文字
    if method == "local":
        log("  使用本地 PaddleOCR")
        raw_text = ocr_with_paddle(pdf_path)
    else:
        # 在线 OCR 需要 API key
        ocr_api_key = getattr(settings, "ocr_space_api_key", "") or "K85730341788957"
        log(f"  使用在线 ocr.space")
        raw_text = await ocr_with_ocr_space(pdf_path, ocr_api_key)

    if not raw_text or len(raw_text.strip()) < 50:
        log(f"  OCR 结果为空或过短，跳过")
        return {"label": label, "questions": 0, "imported": False}

    raw_text = clean_text(raw_text)
    log(f"  OCR 文本长度: {len(raw_text)} 字")

    # AI 结构化
    chunks = chunk_text(raw_text)
    log(f"  分为 {len(chunks)} 个 chunk")

    all_questions = []
    for i, chunk in enumerate(chunks):
        log(f"  AI 结构化 chunk {i+1}/{len(chunks)} ({len(chunk)} 字)...")
        try:
            questions = await call_deepseek(chunk, exam_info, settings)
            all_questions.extend(questions)
            log(f"    提取到 {len(questions)} 道题")
        except Exception as e:
            log(f"    错误: {e}")

    if not all_questions:
        log(f"  未提取到题目")
        return {"label": label, "questions": 0, "imported": False}

    # 去重
    seen = {}
    for q in all_questions:
        qno = str(q.get("question_no", "")).strip()
        if qno and qno not in seen:
            seen[qno] = q
    questions = sorted(seen.values(), key=lambda q: int(re.findall(r"\d+", q.get("question_no", "0"))[0]) if re.findall(r"\d+", q.get("question_no", "0")) else 0)

    for q in questions:
        q["is_verified"] = False

    # 构建 payload
    payload = {
        "exam": {
            "exam_name": "网络工程师",
            "level": "中级",
            "year": exam_info["year"],
            "season": exam_info["season"],
            "paper_type": exam_info["paper_type"],
            "source_name": f"OCR 提取 - {exam_info['year']}年{exam_info['season']}",
            "source_url": "",
            "is_memory_version": False,
            "remark": f"从扫描版 PDF 通过 OCR 自动提取，未经人工校对",
        },
        "questions": questions,
    }

    # 保存 JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{exam_info['year']}_{exam_info['season']}_{exam_info['paper_type']}_ocr.json"
    filename = filename.replace("/", "_").replace(" ", "_")
    out_path = OUTPUT_DIR / filename
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  已保存: {out_path} ({len(questions)} 道题)")

    # 导入
    imported = False
    if do_import:
        try:
            import_payload_data = load_import_payload(out_path)
            with SessionLocal() as db:
                result = import_payload(
                    db,
                    import_payload_data,
                    source_file=str(out_path),
                    source_type="pdf-ocr",
                    update_existing=False,
                    force_unverified=True,
                )
            log(f"  导入完成: 新增 {result.success_count}, 跳过 {result.skipped_count}, 失败 {result.failed_count}")
            imported = True
        except Exception as e:
            log(f"  导入失败: {e}")

    return {"label": label, "questions": len(questions), "imported": imported}


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()

    if not settings.deepseek_api_key or "请在本地" in settings.deepseek_api_key:
        log("错误: 未配置 DEEPSEEK_API_KEY")
        return 1

    # 扫描需要 OCR 的 PDF
    pdfs = scan_scanned_pdfs(args.year)
    if not pdfs:
        log("未找到需要 OCR 的扫描版 PDF")
        return 1

    do_import = args.import_db
    method = args.method

    log(f"模式: {'导入数据库' if do_import else '仅输出 JSON'}")
    log(f"OCR 方法: {method}")
    log("")

    total_questions = 0
    total_imported = 0
    errors = 0

    for exam_info in pdfs:
        try:
            result = await process_one(exam_info, settings, do_import, method)
            total_questions += result["questions"]
            if result["imported"]:
                total_imported += 1
        except Exception as e:
            log(f"  处理失败: {e}")
            errors += 1
        log("")

    log("=" * 50)
    log(f"处理完成: {len(pdfs)} 个扫描版 PDF, {total_questions} 道题, {errors} 个错误")
    if do_import:
        log(f"已导入: {total_imported} 个试卷")
    return 0 if errors == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描版 PDF OCR 提取")
    parser.add_argument("--year", type=int, default=None, help="只处理指定年份")
    parser.add_argument("--dry-run", action="store_true", help="只输出 JSON（默认）")
    parser.add_argument("--import", dest="import_db", action="store_true", help="导入数据库")
    parser.add_argument("--method", choices=["online", "local"], default="online", help="OCR 方法: online(ocr.space) 或 local(PaddleOCR)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.import_db:
        args.dry_run = True
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
