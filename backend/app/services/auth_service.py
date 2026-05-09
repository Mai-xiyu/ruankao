import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthSession, User

SESSION_COOKIE = "rk_session"
SESSION_DAYS = 30
GUEST_SESSION_DAYS = 14

try:
    from passlib.context import CryptContext

    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:  # pragma: no cover - fallback keeps local dev usable before pip install.
    _pwd_context = None


@dataclass
class AuthIdentity:
    user: User | None
    guest_session_id: str | None
    session: AuthSession

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        return expires_at <= datetime.utcnow()
    return expires_at <= utc_now()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if _pwd_context is not None:
        return _pwd_context.hash(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        _, salt, digest = password_hash.split("$", 2)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000).hex()
        return secrets.compare_digest(actual, digest)
    if _pwd_context is None:
        return False
    return _pwd_context.verify(password, password_hash)


def find_user_for_login(db: Session, username_or_email: str) -> User | None:
    value = username_or_email.strip()
    return db.execute(
        select(User).where(or_(User.username == value, User.email == value.lower()))
    ).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: str | None,
    display_name: str | None,
    role: str = "user",
) -> User:
    normalized = username.strip()
    conditions = [User.username == normalized]
    if email:
        conditions.append(User.email == email)
    existing = db.execute(select(User).where(or_(*conditions))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已存在")
    user = User(
        username=normalized,
        email=email,
        display_name=display_name.strip() if display_name else normalized,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def create_auth_session(
    db: Session,
    response: Response,
    *,
    user: User | None = None,
    guest_session_id: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, AuthSession]:
    token = _new_token()
    is_guest = user is None
    expires_at = utc_now() + timedelta(days=GUEST_SESSION_DAYS if is_guest else SESSION_DAYS)
    session = AuthSession(
        token_hash=hash_token(token),
        user_id=user.id if user else None,
        guest_session_id=guest_session_id or (secrets.token_hex(16) if is_guest else None),
        expires_at=expires_at,
        user_agent=user_agent,
    )
    db.add(session)
    db.flush()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        max_age=int((expires_at - utc_now()).total_seconds()),
        path="/",
    )
    return token, session


def get_session_by_token(db: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    session = db.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token))).scalar_one_or_none()
    if not session or session.revoked_at is not None or _is_expired(session.expires_at):
        return None
    session.last_seen_at = utc_now()
    return session


def identity_from_session(session: AuthSession) -> AuthIdentity:
    return AuthIdentity(user=session.user, guest_session_id=session.guest_session_id, session=session)


def ensure_identity(request: Request, response: Response, db: Session) -> AuthIdentity:
    session = get_session_by_token(db, request.cookies.get(SESSION_COOKIE))
    if session:
        return identity_from_session(session)
    _, session = create_auth_session(db, response, user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(session)
    return identity_from_session(session)


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
