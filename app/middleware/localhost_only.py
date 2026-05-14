from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app import config

STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


def _token_authed(request) -> bool:
    """Returns True if request carries a valid access token (re-read from .env each call)."""
    access_token = config.env().get("CONTROL_PANEL_ACCESS_TOKEN", "")
    if not access_token:
        return False
    provided = request.headers.get("x-cp-token") or request.query_params.get("token")
    return bool(provided and provided == access_token)


class LocalhostOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Static assets carry no sensitive data — let them through unconditionally so
        # the browser can load CSS/JS after the initial token-authenticated page load.
        if request.url.path.startswith("/static/"):
            response = await call_next(request)
            _set_security_headers(response)
            return response

        # Allow requests authenticated with the access token (remote / tunnel access).
        if _token_authed(request):
            response = await call_next(request)
            _set_security_headers(response)
            return response

        host = request.headers.get("host", "")
        if host not in config.ALLOWED_HOSTS:
            return JSONResponse({"error": "host_not_allowed"}, status_code=403)

        origin = request.headers.get("origin")
        if origin and origin not in config.ALLOWED_ORIGINS:
            return JSONResponse({"error": "origin_not_allowed"}, status_code=403)

        if request.method in STATE_CHANGING:
            if origin is None:
                return JSONResponse({"error": "origin_required"}, status_code=403)
            from app.main import _read_csrf
            expected = _read_csrf()
            provided = request.headers.get("x-tk-cp-csrf")
            if not provided or provided != expected:
                return JSONResponse({"error": "csrf_mismatch"}, status_code=403)

        response = await call_next(request)
        _set_security_headers(response)
        return response


def _set_security_headers(response) -> None:
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
