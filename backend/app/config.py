from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    """Uygulama genelinde kullanılan konfigürasyon değerleri."""

    # Genel
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Sentry
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    # CORS
    allowed_origins: List[str] = Field(
        default_factory=list,
        alias="ALLOWED_ORIGINS",
        description="Virgülle ayrılmış origin listesi",
    )

    # LLM / Gemini
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_model: Optional[str] = Field(default=None, alias="GEMINI_MODEL")

    # NLP / Embeddings
    use_embeddings: bool = Field(default=True, alias="USE_EMBEDDINGS")

    # Harici servisler
    openweather_api_key: Optional[str] = Field(default=None, alias="OPENWEATHER_API_KEY")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # Admin / güvenlik
    admin_secret_token: Optional[str] = Field(default=None, alias="ADMIN_SECRET_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allowed_origins(self) -> List[str]:
        """CORS için origin listesini döndür.

        Env tanımlıysa onu kullanır, yoksa development için güvenli varsayılanlara düşer.
        """
        if self.allowed_origins:
            # Env'den geldiğinde tek string olabilir, virgüle göre böl
            if len(self.allowed_origins) == 1 and isinstance(self.allowed_origins[0], str):
                raw = self.allowed_origins[0]
                return [o.strip() for o in raw.split(",") if o.strip()]
            return self.allowed_origins

        # Varsayılan geliştirme origin'leri
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://egemenulker.com",
            "https://www.egemenulker.com",
            "https://king-prawn-app-t5y4u.ondigitalocean.app",
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings singleton'ını döndür."""
    return Settings()


settings = get_settings()

