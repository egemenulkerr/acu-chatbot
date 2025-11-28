from __future__ import annotations

from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # Pydantic v1 fallback

from pydantic import Field


class Settings(BaseSettings):
    google_api_key: str | None = Field(
        default=None,
        env="GOOGLE_API_KEY",
        description="Google Gemini API anahtarı",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        env="GEMINI_MODEL",
        description="Kullanılacak Gemini modeli",
    )
    allowed_origins: list[str] | None = Field(
        default=None,
        env="ALLOWED_ORIGINS",
        description="CORS için izin verilen origin'ler (virgülle ayrılmış)",
    )
    backend_url: str | None = Field(
        default=None,
        env="BACKEND_URL",
        description="Backend API URL'i (frontend için)",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # ALLOWED_ORIGINS string'ini list'e çevir
        if isinstance(self.allowed_origins, str):
            self.allowed_origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

