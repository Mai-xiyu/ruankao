from fastapi import APIRouter

from app.schemas.ai import (
    AIExtractRequest,
    AIGenerateQuestionsRequest,
    AIImproveAnalysisRequest,
    AISourceAuditRequest,
    AISourceAuditResult,
    AISuggestTagsRequest,
)
from app.schemas.importing import ImportPayload
from app.services.ai_service import DeepSeekService

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/extract-questions", response_model=ImportPayload)
async def extract_questions(payload: AIExtractRequest) -> ImportPayload:
    service = DeepSeekService()
    exam = payload.exam.model_dump() if payload.exam else None
    return await service.extract_questions(payload.text, exam, payload.use_reasoning_model)


@router.post("/generate-questions", response_model=ImportPayload)
async def generate_questions(payload: AIGenerateQuestionsRequest) -> ImportPayload:
    service = DeepSeekService()
    return await service.generate_questions(
        exam=payload.exam.model_dump(),
        question_count=payload.question_count,
        question_types=payload.question_types,
        difficulty=payload.difficulty,
        knowledge_areas=payload.knowledge_areas,
        tags=payload.tags,
        source_text=payload.source_text,
        extra_requirements=payload.extra_requirements,
        use_reasoning_model=payload.use_reasoning_model,
    )


@router.post("/suggest-tags")
async def suggest_tags(payload: AISuggestTagsRequest) -> dict:
    service = DeepSeekService()
    return await service.suggest_tags(payload.stem, payload.answer, payload.analysis, payload.use_reasoning_model)


@router.post("/improve-analysis")
async def improve_analysis(payload: AIImproveAnalysisRequest) -> dict:
    service = DeepSeekService()
    return await service.improve_analysis(payload.stem, payload.answer, payload.analysis, payload.use_reasoning_model)


@router.post("/audit-source", response_model=AISourceAuditResult)
async def audit_source(payload: AISourceAuditRequest) -> AISourceAuditResult:
    service = DeepSeekService()
    exam = payload.exam.model_dump() if payload.exam else None
    return await service.audit_source(
        url=payload.url,
        title=payload.title,
        content=payload.content,
        exam=exam,
        year=payload.year,
        season=payload.season,
        paper_type=payload.paper_type,
        use_reasoning_model=payload.use_reasoning_model,
    )
