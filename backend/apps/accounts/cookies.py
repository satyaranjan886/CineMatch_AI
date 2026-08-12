"""JWT refresh-token cookie helpers."""

from __future__ import annotations

from django.conf import settings

REFRESH_COOKIE_NAME = getattr(settings, "JWT_REFRESH_COOKIE_NAME", "cinematch_refresh")


def refresh_cookie_kwargs() -> dict:
    secure = bool(getattr(settings, "JWT_REFRESH_COOKIE_SECURE", settings.SESSION_COOKIE_SECURE))
    # Cross-site SPAs need None+Secure; same-site (Next rewrite) can use Lax.
    same_site = getattr(settings, "JWT_REFRESH_COOKIE_SAMESITE", "Lax")
    return {
        "key": REFRESH_COOKIE_NAME,
        "httponly": True,
        "secure": secure,
        "samesite": same_site,
        "path": getattr(settings, "JWT_REFRESH_COOKIE_PATH", "/"),
        "max_age": int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    }


def set_refresh_cookie(response, refresh_token: str) -> None:
    kwargs = refresh_cookie_kwargs()
    response.set_cookie(value=refresh_token, **kwargs)


def clear_refresh_cookie(response) -> None:
    kwargs = refresh_cookie_kwargs()
    response.delete_cookie(
        key=kwargs["key"],
        path=kwargs["path"],
        samesite=kwargs["samesite"],
    )


def get_refresh_token_from_request(request) -> str | None:
    body_token = None
    if hasattr(request, "data"):
        body_token = request.data.get("refresh")
    if body_token:
        return str(body_token)
    cookie = request.COOKIES.get(REFRESH_COOKIE_NAME)
    return str(cookie) if cookie else None
