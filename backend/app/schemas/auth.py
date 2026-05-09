from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        text = value.strip().lower()
        if "@" not in text:
            raise ValueError("邮箱格式不正确")
        return text


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AuthMeResponse(BaseModel):
    authenticated: bool
    guest_session_id: str | None = None
    user: UserOut | None = None


class AuthTokenResponse(AuthMeResponse):
    expires_at: datetime
