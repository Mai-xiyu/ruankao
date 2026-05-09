from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.schemas.importing import ImportPayload, ImportResult
from app.services.import_service import import_payload

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/json", response_model=ImportResult)
def import_json(
    payload: ImportPayload,
    update_existing: bool = Query(default=False),
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportResult:
    return import_payload(db, payload, source_file="api-json", source_type="json", update_existing=update_existing)


@router.post("/ai-json", response_model=ImportResult)
def import_ai_json(
    payload: ImportPayload,
    update_existing: bool = Query(default=False),
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportResult:
    return import_payload(
        db,
        payload,
        source_file="api-ai-json",
        source_type="ai-json",
        update_existing=update_existing,
        force_unverified=True,
    )


@router.post("/ai-generated", response_model=ImportResult)
def import_ai_generated(
    payload: ImportPayload,
    update_existing: bool = Query(default=False),
    _admin: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportResult:
    return import_payload(
        db,
        payload,
        source_file="api-ai-generated",
        source_type="ai-generated",
        update_existing=update_existing,
        force_unverified=True,
    )
