from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthIdentity, ensure_identity


def get_identity(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthIdentity:
    return ensure_identity(request, response, db)


def require_admin(identity: AuthIdentity = Depends(get_identity)) -> AuthIdentity:
    if not identity.user or identity.user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return identity
