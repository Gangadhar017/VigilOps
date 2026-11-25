"""Public address of the demonstration application (OrbitCrate) on the API port.

In the Compose stack the reverse proxy routes ``/orbitcrate/`` straight to the
demonstration application and this module stays switched off.  A host that
offers one public port and no reverse proxy (deploy/render) cannot do that, so
there the API passes the visitor-facing part of the store through instead
(``SERVE_DEMO_APP=true``).

Only the storefront page, its static files and its store API are passed on.
The application's control endpoints (``/internal/*``), ``/metrics`` and
``/health/*`` are never reachable this way.  No credentials, cookies or query
strings are forwarded, the request body is limited to a few kilobytes and each
client address is rate limited.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter

logger = logging.getLogger(__name__)

PUBLIC_PATH = "/orbitcrate"
MAX_BODY_BYTES = 4096
UPSTREAM_TIMEOUT_SECONDS = 10.0

# The page (""), files below static/ and the store API below api/ - nothing else.
_ALLOWED_PATH = re.compile(r"^(?:static|api)/[A-Za-z0-9._/-]{1,120}$")
_REQUEST_HEADERS = ("accept", "content-type", "x-session-id")
_RESPONSE_HEADERS = (
    "content-type", "cache-control", "retry-after", "etag", "last-modified", "content-security-policy",
)
requests_per_client = SlidingWindowLimiter(300, 60)

# Shown when the store does not answer at all.  Where every component runs in one
# container the API opens its port first, so for a few seconds after a start (or
# while the store is being restarted) a visitor reaches the API but not the store.
# The page asks again by itself instead of leaving the visitor with an error.
RETRY_SECONDS = 5
_UNAVAILABLE_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    f'<meta http-equiv="refresh" content="{RETRY_SECONDS}">'
    "<title>OrbitCrate is starting</title></head>"
    '<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0c1533;color:#f4f6fb;'
    'font-family:system-ui,-apple-system,Segoe UI,sans-serif;text-align:center;padding:24px">'
    '<main style="max-width:34rem"><h1 style="font-size:28px;margin:0 0 10px">OrbitCrate is not answering yet</h1>'
    '<p style="margin:0;color:#b7c2da;line-height:1.55">The demonstration application is starting or being restarted. '
    f"This page asks again every {RETRY_SECONDS} seconds and shows the store as soon as it answers.</p>"
    "</main></body></html>"
)

router = APIRouter(include_in_schema=False)
_client: Optional[httpx.AsyncClient] = None


def is_allowed(path: str) -> bool:
    """May this path below the public address be passed to the store?"""
    if path == "":
        return True
    if not _ALLOWED_PATH.match(path):
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))


async def fetch(method: str, path: str, headers: Dict[str, str], body: bytes) -> httpx.Response:
    """One request to the demonstration application (replaced in tests)."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS, follow_redirects=False)
    return await _client.request(
        method, f"{settings.DEMO_APP_URL.rstrip('/')}/{path}", headers=headers, content=body or None
    )


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@router.api_route(PUBLIC_PATH, methods=["GET"])
@router.api_route(PUBLIC_PATH + "/{path:path}", methods=["GET", "POST"])
async def store(request: Request, path: str = "") -> Response:
    if not settings.SERVE_DEMO_APP or not is_allowed(path):
        return _not_found()
    if request.method == "POST" and not path.startswith("api/"):
        return JSONResponse(status_code=405, content={"detail": "Method Not Allowed"})

    client = request.client.host if request.client else "unknown"
    allowed, retry_after = requests_per_client.allow(client)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests to the demonstration application. Please slow down."},
            headers={"Retry-After": str(retry_after)},
        )

    declared = request.headers.get("content-length", "0")
    if not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    body = b""
    if request.method == "POST":
        # Read in pieces and stop at the limit: a body sent without a declared
        # length must not be buffered whole before it is refused.
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})

    headers = {name: request.headers[name] for name in _REQUEST_HEADERS if name in request.headers}
    wants_page = path == ""
    try:
        upstream = await fetch(request.method, path, headers, body)
    except httpx.HTTPError as exc:
        logger.warning("demonstration application not reachable", extra={"error": exc.__class__.__name__})
        retry = {"Cache-Control": "no-store", "Retry-After": str(RETRY_SECONDS)}
        if wants_page:
            return HTMLResponse(_UNAVAILABLE_PAGE, status_code=502, headers=retry)
        return JSONResponse(
            status_code=502, content={"detail": "The demonstration application is not reachable."}, headers=retry
        )

    content = upstream.content
    if wants_page and upstream.headers.get("content-type", "").startswith("text/html"):
        # The page uses relative addresses.  The base element keeps them below the
        # public path whether or not the visitor typed the trailing slash.
        content = content.replace(b"<head>", f'<head>\n  <base href="{PUBLIC_PATH}/">'.encode(), 1)
    passed = {name: upstream.headers[name] for name in _RESPONSE_HEADERS if name in upstream.headers}
    return Response(content=content, status_code=upstream.status_code, headers=passed)
