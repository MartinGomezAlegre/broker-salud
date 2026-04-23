from ipaddress import ip_address

from fastapi import Request
from slowapi import Limiter

from app.settings import get_settings

settings = get_settings()


def _is_trusted_proxy(host: str | None) -> bool:
    if not host:
        return False

    try:
        parsed = ip_address(host)
        return parsed.is_private or parsed.is_loopback
    except ValueError:
        return host in {"localhost"}


def get_client_ip(request: Request) -> str:
    client_host = request.client.host if request.client and request.client.host else None

    if _is_trusted_proxy(client_host):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            forwarded_ip = forwarded_for.split(",")[0].strip()
            if forwarded_ip:
                return forwarded_ip

        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip

    if client_host:
        return client_host

    return "unknown"


limiter_kwargs = {}
if settings.redis_url:
    limiter_kwargs["storage_uri"] = settings.redis_url

limiter = Limiter(key_func=get_client_ip, headers_enabled=True, **limiter_kwargs)
