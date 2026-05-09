from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import AuthLoginRequest, AuthMeResponse, AuthRegisterRequest, AuthTokenResponse, UserOut
from app.services.auth_service import (
    SESSION_COOKIE,
    clear_session,
    create_auth_session,
    create_user,
    find_user_for_login,
    get_session_by_token,
    identity_from_session,
    utc_now,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _response_from_session(session) -> AuthTokenResponse:
    identity = identity_from_session(session)
    return AuthTokenResponse(
        authenticated=identity.is_authenticated,
        guest_session_id=identity.guest_session_id,
        user=UserOut.model_validate(identity.user) if identity.user else None,
        expires_at=session.expires_at,
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = create_user(
        db,
        username=payload.username,
        password=payload.password,
        email=payload.email,
        display_name=payload.display_name,
    )
    _, session = create_auth_session(db, response, user=user, user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return _response_from_session(session)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: AuthLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = find_user_for_login(db, payload.username)
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    _, session = create_auth_session(db, response, user=user, user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(session)
    return _response_from_session(session)


@router.post("/guest-session", response_model=AuthTokenResponse)
def guest_session(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthTokenResponse:
    session = get_session_by_token(db, request.cookies.get(SESSION_COOKIE))
    if session and session.user_id is None:
        return _response_from_session(session)
    _, session = create_auth_session(db, response, user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(session)
    return _response_from_session(session)


@router.get("/me", response_model=AuthMeResponse)
def me(request: Request, db: Session = Depends(get_db)) -> AuthMeResponse:
    session = get_session_by_token(db, request.cookies.get(SESSION_COOKIE))
    if not session:
        return AuthMeResponse(authenticated=False)
    identity = identity_from_session(session)
    return AuthMeResponse(
        authenticated=identity.is_authenticated,
        guest_session_id=identity.guest_session_id,
        user=UserOut.model_validate(identity.user) if identity.user else None,
    )


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    session = get_session_by_token(db, request.cookies.get(SESSION_COOKIE))
    if session:
        session.revoked_at = utc_now()
        db.commit()
    clear_session(response)
    return {"ok": True}
