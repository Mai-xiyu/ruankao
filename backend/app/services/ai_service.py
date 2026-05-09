import json
from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.ai import AISourceAuditResult
from app.schemas.importing import ImportPayload


def _normalize_difficulty(value: Any) -> int:
    if isinstance(value, int):
        return min(5, max(1, value))
    text = str(value or "").strip().lower()
    mapping = {
        "easy": 1,
        "简单": 1,
        "low": 2,
        "medium": 3,
        "中等": 3,
        "normal": 3,
        "hard": 4,
        "困难": 4,
        "high": 4,
        "very hard": 5,
        "极难": 5,
    }
    if text in mapping:
        return mapping[text]
    try:
        return min(5, max(1, int(float(text))))
    except ValueError:
        return 3


def _normalize_options(value: Any) -> dict | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}
    if isinstance(value, list):
        options: dict[str, str] = {}
        fallback_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for index, item in enumerate(value):
            text = str(item).strip()
            if not text:
                continue
            label = fallback_labels[index] if index < len(fallback_labels) else str(index + 1)
            for prefix in (".", "．", "、", " "):
                marker = f"{label}{prefix}"
                if text.upper().startswith(marker.upper()):
                    text = text[len(marker) :].strip()
                    break
            options[label] = text
        return options or None
    return None


def _normalize_import_result(raw: dict[str, Any], exam_hint: dict | None) -> dict[str, Any]:
    data = dict(raw)
    if exam_hint and not data.get("exam"):
        data["exam"] = exam_hint
    questions = data.get("questions") or []
    normalized_questions = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        question = dict(item)
        question["question_no"] = str(question.get("question_no", "")).strip()
        question["question_type"] = str(question.get("question_type") or "single_choice").strip()
        question["options"] = _normalize_options(question.get("options"))
        question["difficulty"] = _normalize_difficulty(question.get("difficulty"))
        tags = question.get("tags") or []
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.replace("，", ",").split(",")]
        question["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
        question["is_verified"] = False
        normalized_questions.append(question)
    data["questions"] = normalized_questions
    return data


class DeepSeekService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _ensure_enabled(self) -> None:
        api_key = self.settings.deepseek_api_key.strip()
        if not self.settings.ai_enabled:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 功能未启用")
        if not api_key or "请在本地" in api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未配置 DEEPSEEK_API_KEY")

    async def _chat_json(
        self,
        messages: list[dict[str, str]],
        use_reasoning_model: bool = False,
        temperature: float = 0.2,
        timeout_seconds: float = 60,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        model = self.settings.deepseek_reasoning_model if use_reasoning_model else self.settings.deepseek_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(self.settings.deepseek_chat_url, headers=headers, json=payload)
        if response.status_code >= 400:
            detail = response.text[:800]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"DeepSeek API 调用失败，HTTP {response.status_code}: {detail}",
            )
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI 返回不是合法 JSON：{exc}") from exc

    async def extract_questions(self, text: str, exam: dict | None, use_reasoning_model: bool = False) -> ImportPayload:
        system = (
            "你是软考多科目题库整理助手。"
            "只把用户提供且声明合法来源的内容结构化为 JSON，不补造不存在的题目。"
            "如果提供了 exam_hint，必须按其中的 level、exam_name、year、season、paper_type 组织输出。"
            "输出必须是合法 JSON 对象，格式为 {\"exam\":{...},\"questions\":[...]}。"
            "questions 字段使用 question_no, question_type, stem, options, answer, analysis, "
            "difficulty, knowledge_area, tags, is_verified。"
            "question_no 必须是字符串；options 必须是对象或 null；difficulty 必须是 1 到 5 的整数。"
            "所有 is_verified 必须为 false。"
        )
        user = {
            "exam_hint": exam,
            "content": text,
            "allowed_question_types": ["single_choice", "multiple_choice", "fill_blank", "case", "config", "calculation"],
        }
        result = await self._chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            use_reasoning_model=use_reasoning_model,
        )
        result = _normalize_import_result(result, exam)
        try:
            payload = ImportPayload.model_validate(result)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI JSON 未通过结构校验：{exc}") from exc
        for question in payload.questions:
            question.is_verified = False
        return payload

    async def generate_questions(
        self,
        *,
        exam: dict,
        question_count: int,
        question_types: list[str],
        difficulty: int,
        knowledge_areas: list[str],
        tags: list[str],
        source_text: str | None,
        extra_requirements: str | None,
        use_reasoning_model: bool = False,
    ) -> ImportPayload:
        exam_hint = dict(exam)
        exam_hint["source_name"] = exam_hint.get("source_name") or "DeepSeek AI 生成"
        exam_hint["source_url"] = exam_hint.get("source_url") or None
        remark = (exam_hint.get("remark") or "").strip()
        ai_remark = "AI 生成模拟练习题，非历年真题，需要人工校对"
        exam_hint["remark"] = f"{remark}；{ai_remark}" if remark else ai_remark

        system = (
            "你是软考多科目模拟题命题助手。"
            "只能生成原创练习题或模拟题，不得声称是历年真题或官方答案，不得大段复制用户提供的来源文本。"
            "如果提供教材、大纲或知识点文本，只能提炼考点后重新命题。"
            "题目必须贴合 exam.level 和 exam.exam_name，答案唯一或按题型清晰可判定，解析说明关键依据。"
            "输出必须是合法 JSON 对象，格式为 {\"exam\":{...},\"questions\":[...]}。"
            "questions 字段使用 question_no, question_type, stem, options, answer, analysis, "
            "difficulty, knowledge_area, tags, is_verified。"
            "question_no 必须是字符串；options 必须是对象或 null；difficulty 必须是 1 到 5 的整数。"
            "所有 is_verified 必须为 false。"
        )
        user = {
            "exam": exam_hint,
            "question_count": question_count,
            "question_types": question_types,
            "difficulty": difficulty,
            "knowledge_areas": knowledge_areas,
            "tags": tags,
            "extra_requirements": extra_requirements,
            "source_text": source_text,
            "allowed_question_types": ["single_choice", "multiple_choice", "fill_blank", "case", "config", "calculation"],
        }
        result = await self._chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            use_reasoning_model=use_reasoning_model,
            temperature=0.45,
            timeout_seconds=120,
        )
        result = _normalize_import_result(result, exam_hint)
        try:
            payload = ImportPayload.model_validate(result)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI JSON 未通过结构校验：{exc}") from exc
        for index, question in enumerate(payload.questions, start=1):
            question.question_no = question.question_no or str(index)
            question.difficulty = difficulty
            question.is_verified = False
        return payload

    async def suggest_tags(
        self,
        stem: str,
        answer: str | None,
        analysis: str | None,
        use_reasoning_model: bool = False,
    ) -> dict[str, Any]:
        system = (
            "你是软考多科目题库标签助手。"
            "基于题干、答案和解析判断知识点、标签和难度；不要声称结果来自官方。"
            "输出必须是合法 JSON 对象：knowledge_area 字符串，difficulty 1-5 整数，tags 字符串数组。"
        )
        user = {"stem": stem, "answer": answer, "analysis": analysis}
        result = await self._chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            use_reasoning_model=use_reasoning_model,
        )
        difficulty = int(result.get("difficulty", 3))
        result["difficulty"] = min(5, max(1, difficulty))
        result["tags"] = [str(tag).strip() for tag in result.get("tags", []) if str(tag).strip()]
        return result

    async def improve_analysis(
        self,
        stem: str,
        answer: str | None,
        analysis: str | None,
        use_reasoning_model: bool = False,
    ) -> dict[str, Any]:
        system = (
            "你是软考多科目解析维护助手。"
            "基于题干和答案润色解析，不改变题意，不编造无法判断的事实，不把推断答案描述为官方答案。"
            "输出必须是合法 JSON 对象：analysis 字符串。"
        )
        user = {"stem": stem, "answer": answer, "analysis": analysis}
        result = await self._chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            use_reasoning_model=use_reasoning_model,
        )
        return {"analysis": str(result.get("analysis", "")).strip()}

    async def audit_source(
        self,
        *,
        url: str,
        title: str | None,
        content: str,
        exam: dict | None,
        year: int | None,
        season: str | None,
        paper_type: str | None,
        use_reasoning_model: bool = False,
    ) -> AISourceAuditResult:
        system = (
            "你是题库来源合规与质量初筛助手。"
            "你不能替代法律判断，只能基于页面文本做保守风险初筛。"
            "只有页面正文明确出现开放授权、公开许可、官方样题、可转载或用户自有来源等信号时，"
            "can_auto_import 才能为 true。"
            "未知版权、培训机构题库、下载站、论坛转载、需要登录/付费/验证码的来源必须标为 "
            "medium 或 high，can_auto_import=false。"
            "如果内容和 exam_hint 或指定年份/季节/卷型不相关，relevant=false。"
            "输出必须是合法 JSON 对象，字段为 relevant, can_structure, risk_level, license_signal, "
            "can_auto_import, reason, suggested_action, extracted_year, extracted_season。"
        )
        user = {
            "url": url,
            "title": title,
            "exam_hint": exam,
            "target_year": year,
            "target_season": season,
            "target_paper_type": paper_type,
            "content_excerpt": content[:60000],
        }
        raw = await self._chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            use_reasoning_model=use_reasoning_model,
        )
        risk = str(raw.get("risk_level", "high")).lower()
        if risk not in {"low", "medium", "high"}:
            risk = "high"
        result = {
            "relevant": bool(raw.get("relevant", False)),
            "can_structure": bool(raw.get("can_structure", False)),
            "risk_level": risk,
            "license_signal": str(raw.get("license_signal", "unknown"))[:200],
            "can_auto_import": bool(raw.get("can_auto_import", False)) and risk == "low",
            "reason": str(raw.get("reason", ""))[:1000],
            "suggested_action": str(raw.get("suggested_action", "manual_review"))[:200],
            "extracted_year": raw.get("extracted_year"),
            "extracted_season": raw.get("extracted_season"),
        }
        return AISourceAuditResult.model_validate(result)
