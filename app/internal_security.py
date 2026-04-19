import secrets

from fastapi import Header, HTTPException

from app.settings import get_settings


def require_service_token(
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    settings = get_settings()
    expected = settings.service_token

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="SERVICE_TOKEN no esta configurado para jobs internos.",
        )

    bearer_token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    provided = (x_service_token or bearer_token or "").strip()

    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Service token invalido.")

    return True

