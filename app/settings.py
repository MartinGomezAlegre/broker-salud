from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    secret_key: str
    qr_secret: str
    service_token: str | None
    frontend_url: str
    cors_origins: tuple[str, ...]
    redis_url: str | None
    job_queue_name: str
    job_retry_limit: int
    payment_manual_enabled: bool
    mercadopago_webhook_secret: str | None
    mercadopago_webhook_tolerance_seconds: int
    docs_enabled: bool
    redoc_enabled: bool


def _build_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL no esta configurada")

    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key:
        raise ValueError("SECRET_KEY no esta configurada")

    qr_secret = os.getenv("QR_SECRET", "").strip() or secret_key
    service_token = os.getenv("SERVICE_TOKEN", "").strip() or None
    frontend_url = (os.getenv("FRONTEND_URL", "").strip() or "https://celdoctor-waitlist.vercel.app").rstrip("/")

    default_origins = (
        "http://localhost:3000",
        "http://localhost:3001",
        "https://celdoctor-waitlist.vercel.app",
        "https://celdoctor.com",
        "https://www.celdoctor.com",
    )
    cors_origins = _parse_csv(os.getenv("CORS_ORIGINS")) or default_origins
    redis_url = os.getenv("REDIS_URL", "").strip() or None
    job_queue_name = os.getenv("JOB_QUEUE_NAME", "celdoctor:jobs").strip() or "celdoctor:jobs"
    job_retry_limit = max(0, int(os.getenv("JOB_RETRY_LIMIT", "3")))
    payment_manual_enabled = _parse_bool(
        os.getenv("PAYMENT_MANUAL_ENABLED"),
        default=app_env != "production",
    )
    mercadopago_webhook_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip() or None
    mercadopago_webhook_tolerance_seconds = max(
        30,
        int(os.getenv("MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS", "300")),
    )

    docs_enabled = os.getenv("ENABLE_DOCS", "true").strip().lower() == "true"
    if app_env == "production":
        docs_enabled = False if os.getenv("ENABLE_DOCS") is None else docs_enabled

    redoc_enabled = os.getenv("ENABLE_REDOC", "true").strip().lower() == "true"
    if app_env == "production":
        redoc_enabled = False if os.getenv("ENABLE_REDOC") is None else redoc_enabled

    return Settings(
        app_env=app_env,
        database_url=_normalize_database_url(database_url),
        secret_key=secret_key,
        qr_secret=qr_secret,
        service_token=service_token,
        frontend_url=frontend_url,
        cors_origins=cors_origins,
        redis_url=redis_url,
        job_queue_name=job_queue_name,
        job_retry_limit=job_retry_limit,
        payment_manual_enabled=payment_manual_enabled,
        mercadopago_webhook_secret=mercadopago_webhook_secret,
        mercadopago_webhook_tolerance_seconds=mercadopago_webhook_tolerance_seconds,
        docs_enabled=docs_enabled,
        redoc_enabled=redoc_enabled,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build_settings()
