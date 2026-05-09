from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)


class Settings(BaseModel):
    mysql_admin_host: str = Field(default="10.20.60.167", alias="MYSQL_ADMIN_HOST")
    mysql_admin_port: int = Field(default=3306, alias="MYSQL_ADMIN_PORT")
    mysql_admin_user: str = Field(default="root", alias="MYSQL_ADMIN_USER")
    mysql_admin_password: str = Field(default="", alias="MYSQL_ADMIN_PASSWORD")

    db_host: str = Field(default="10.20.60.167", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_name: str = Field(default="rk_network_engineer", alias="DB_NAME")
    db_user: str = Field(default="rk_bank", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_secret_key: str = Field(default="dev-only-change-me", alias="APP_SECRET_KEY")
    cors_origins: str = Field(default="http://127.0.0.1:5173,http://localhost:5173", alias="CORS_ORIGINS")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")

    ai_enabled: bool = Field(default=True, alias="AI_ENABLED")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_reasoning_model: str = Field(default="deepseek-v4-pro", alias="DEEPSEEK_REASONING_MODEL")

    search_provider: str = Field(default="searxng", alias="SEARCH_PROVIDER")
    searxng_base_url: str = Field(default="", alias="SEARXNG_BASE_URL")
    bing_search_api_key: str = Field(default="", alias="BING_SEARCH_API_KEY")
    bing_search_endpoint: str = Field(default="https://api.bing.microsoft.com/v7.0/search", alias="BING_SEARCH_ENDPOINT")

    ocr_space_api_key: str = Field(default="", alias="OCR_SPACE_API_KEY")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return f"mysql+pymysql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    @property
    def deepseek_chat_url(self) -> str:
        return f"{self.deepseek_base_url.rstrip('/')}/chat/completions"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        MYSQL_ADMIN_HOST=os.getenv("MYSQL_ADMIN_HOST", "10.20.60.167"),
        MYSQL_ADMIN_PORT=os.getenv("MYSQL_ADMIN_PORT", "3306"),
        MYSQL_ADMIN_USER=os.getenv("MYSQL_ADMIN_USER", "root"),
        MYSQL_ADMIN_PASSWORD=os.getenv("MYSQL_ADMIN_PASSWORD", ""),
        DB_HOST=os.getenv("DB_HOST", "10.20.60.167"),
        DB_PORT=os.getenv("DB_PORT", "3306"),
        DB_NAME=os.getenv("DB_NAME", "rk_network_engineer"),
        DB_USER=os.getenv("DB_USER", "rk_bank"),
        DB_PASSWORD=os.getenv("DB_PASSWORD", ""),
        APP_HOST=os.getenv("APP_HOST", "0.0.0.0"),
        APP_PORT=os.getenv("APP_PORT", "8000"),
        APP_DEBUG=os.getenv("APP_DEBUG", "true"),
        APP_SECRET_KEY=os.getenv("APP_SECRET_KEY", "dev-only-change-me"),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"),
        COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false"),
        AI_ENABLED=os.getenv("AI_ENABLED", "true"),
        DEEPSEEK_API_KEY=os.getenv("DEEPSEEK_API_KEY", ""),
        DEEPSEEK_BASE_URL=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        DEEPSEEK_MODEL=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        DEEPSEEK_REASONING_MODEL=os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro"),
        SEARCH_PROVIDER=os.getenv("SEARCH_PROVIDER", "searxng"),
        SEARXNG_BASE_URL=os.getenv("SEARXNG_BASE_URL", ""),
        BING_SEARCH_API_KEY=os.getenv("BING_SEARCH_API_KEY", ""),
        BING_SEARCH_ENDPOINT=os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"),
        OCR_SPACE_API_KEY=os.getenv("OCR_SPACE_API_KEY", ""),
    )
