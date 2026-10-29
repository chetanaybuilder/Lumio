import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "VexoVault"
    ENV: str = os.getenv("ENV", "development")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./vexovault.db"
    )
    DIRECT_DATABASE_URL: Optional[str] = os.getenv(
        "DIRECT_DATABASE_URL",
        None
    )

    # Auth & JWT (HS256, 15 min, issuer vexovault, aud vexovault-api)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "vexovault-super-secret-key-32-characters-minimum-for-security!")
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "vexovault"
    JWT_AUDIENCE: str = "vexovault-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_DOMAIN: Optional[str] = os.getenv("COOKIE_DOMAIN", None)
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    GOOGLE_CLIENT_ID: str = os.getenv(
        "GOOGLE_CLIENT_ID",
        ""
    )
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv(
        "GOOGLE_CLIENT_SECRET",
        None
    )

    # AI (Gemini 2.5 Flash & gemini-embedding-001)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    DAILY_TOKEN_QUOTA: int = 400000

    # Storage (Cloudflare R2)
    R2_ACCOUNT_ID: Optional[str] = os.getenv("R2_ACCOUNT_ID", None)
    R2_ACCESS_KEY_ID: Optional[str] = os.getenv("R2_ACCESS_KEY_ID", None)
    R2_SECRET_ACCESS_KEY: Optional[str] = os.getenv("R2_SECRET_ACCESS_KEY", None)
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "vexovault-documents")
    R2_ENDPOINT_URL: Optional[str] = os.getenv("R2_ENDPOINT_URL", None)

    # CORS & Web
    APP_ORIGIN: str = os.getenv("APP_ORIGIN", "http://localhost:5173")
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

settings = Settings()
