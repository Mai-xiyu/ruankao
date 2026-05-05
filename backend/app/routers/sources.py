from fastapi import APIRouter, HTTPException, status

from app.schemas.ai import SourceConfirmRequest, SourcePreviewRequest
from app.schemas.importing import ImportPayload
from app.services.ai_service import DeepSeekService
from app.services.source_service import preview_source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/preview")
async def source_preview(payload: SourcePreviewRequest) -> dict:
    return await preview_source(payload.text, str(payload.url) if payload.url else None)


@router.post("/confirm-import", response_model=ImportPayload)
async def confirm_import(payload: SourceConfirmRequest) -> ImportPayload:
    if not payload.legal_confirmation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必须确认来源合法后才能进入 AI 结构化流程")
    preview = await preview_source(payload.text, str(payload.url) if payload.url else None)
    service = DeepSeekService()
    exam = payload.exam.model_dump() if payload.exam else None
    return await service.extract_questions(preview["content_excerpt"], exam, payload.use_reasoning_model)

