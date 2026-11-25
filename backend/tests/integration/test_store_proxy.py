"""The demonstration application's public address on the API port (SERVE_DEMO_APP).

Used by the single-container image, which has no reverse proxy in front of the
API.  The store's page, static files and store API are passed through; nothing
else of the demonstration application is.
"""
import httpx
import pytest

from app.api import store
from app.core.config import settings

PAGE = b"<!doctype html><html><head>\n<title>OrbitCrate</title></head><body>store</body></html>"


class Upstream:
    """Records what the API asks the demonstration application for."""

    def __init__(self) -> None:
        self.calls = []
        self.fail = False

    async def __call__(self, method, path, headers, body):
        self.calls.append({"method": method, "path": path, "headers": dict(headers), "body": body})
        if self.fail:
            raise httpx.ConnectError("connection refused")
        request = httpx.Request(method, f"http://demo-app.invalid:8001/{path}")
        if path == "":
            return httpx.Response(
                200, content=PAGE, request=request,
                headers={"content-type": "text/html; charset=utf-8", "set-cookie": "a=b", "x-internal": "1"},
            )
        if path == "api/orders" and method == "POST":
            return httpx.Response(201, json={"id": "OC-TEST01"}, request=request)
        if path == "api/broken":
            return httpx.Response(500, json={"detail": "The store backend failed to answer."}, request=request)
        return httpx.Response(200, json={"path": path}, request=request)


@pytest.fixture
def upstream(monkeypatch):
    fake = Upstream()
    monkeypatch.setattr(store, "fetch", fake)
    monkeypatch.setattr(settings, "SERVE_DEMO_APP", True)
    store.requests_per_client.clear()
    yield fake
    store.requests_per_client.clear()


def test_the_store_is_not_served_unless_switched_on(client, monkeypatch):
    called = []

    async def fetch(*args):
        called.append(args)

    monkeypatch.setattr(store, "fetch", fetch)
    for path in ("/orbitcrate", "/orbitcrate/", "/orbitcrate/api/catalog", "/orbitcrate/static/app.js"):
        assert client.get(path).status_code == 404
    assert called == []


def test_the_page_is_served_with_and_without_the_trailing_slash(client, upstream):
    for address in ("/orbitcrate/", "/orbitcrate"):
        response = client.get(address, follow_redirects=False)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        # Relative addresses of the page stay below the public path either way.
        assert '<base href="/orbitcrate/">' in response.text
        assert "store</body>" in response.text
    assert [call["path"] for call in upstream.calls] == ["", ""]


def test_store_requests_are_passed_on_with_only_the_headers_the_store_needs(client, upstream):
    response = client.post(
        "/orbitcrate/api/orders?debug=1",
        json={"plan": "crate-m"},
        headers={"X-Session-Id": "visitor-session-1", "Authorization": "Bearer secret", "Cookie": "session=abc"},
    )
    assert response.status_code == 201 and response.json() == {"id": "OC-TEST01"}
    call = upstream.calls[-1]
    assert call["method"] == "POST" and call["path"] == "api/orders"  # the query string is dropped
    assert call["body"] == b'{"plan":"crate-m"}' or call["body"] == b'{"plan": "crate-m"}'
    assert sorted(call["headers"]) == ["accept", "content-type", "x-session-id"]

    page = client.get("/orbitcrate/")
    assert "set-cookie" not in page.headers and "x-internal" not in page.headers


def test_upstream_failures_reach_the_visitor_unchanged(client, upstream):
    response = client.get("/orbitcrate/api/broken")
    assert response.status_code == 500
    assert response.json() == {"detail": "The store backend failed to answer."}


@pytest.mark.parametrize(
    "path",
    [
        "internal/state", "internal/fault", "internal/recover", "metrics", "health", "health/ready", "health/live",
        "static/../internal/state", "api/../internal/state", "api/%2e%2e/internal/state", "api//orders",
        "docs", "openapi.json", "static/", "api/", "api/orders?x", "static/app.js\\..\\x",
    ],
)
def test_nothing_but_the_page_static_files_and_the_store_api_is_reachable(client, upstream, path):
    assert client.get(f"/orbitcrate/{path}").status_code in (404, 200)
    for call in upstream.calls:
        # Whatever was passed on stayed inside the visitor-facing part of the store.
        assert call["path"] == "" or call["path"].startswith(("static/", "api/"))
        assert ".." not in call["path"] and "//" not in call["path"] and "\\" not in call["path"]
        assert not call["path"].startswith(("internal", "metrics", "health"))


def test_internal_paths_never_reach_the_demonstration_application(client, upstream):
    for path in ("internal/state", "metrics", "health/ready", "static/../internal/state", "api/%2e%2e/metrics"):
        response = client.get(f"/orbitcrate/{path}")
        assert response.status_code == 404, path
        response = client.post(f"/orbitcrate/{path}", json={"mode": "outage"})
        assert response.status_code in (404, 405), path
    assert upstream.calls == []


def test_only_the_store_api_accepts_posts_and_bodies_are_small(client, upstream):
    assert client.post("/orbitcrate/static/app.js", content=b"x").status_code == 405
    assert client.post("/orbitcrate/", content=b"x").status_code == 405
    assert client.put("/orbitcrate/api/orders", json={}).status_code == 405
    assert client.delete("/orbitcrate/api/orders/OC-1").status_code == 405
    assert upstream.calls == []

    too_large = client.post("/orbitcrate/api/orders", content=b"x" * (store.MAX_BODY_BYTES + 1))
    assert too_large.status_code == 413
    assert upstream.calls == []


def test_an_unreachable_store_gives_a_page_that_asks_again_by_itself(client, upstream):
    """After a start the API answers a few seconds before the store does."""
    upstream.fail = True
    page = client.get("/orbitcrate/", headers={"Accept": "text/html"})
    assert page.status_code == 502 and "not answering yet" in page.text
    assert f'<meta http-equiv="refresh" content="{store.RETRY_SECONDS}">' in page.text
    assert page.headers["retry-after"] == str(store.RETRY_SECONDS)
    assert page.headers["cache-control"] == "no-store"
    # No script and nothing loaded from elsewhere: the page works under any content policy.
    assert "<script" not in page.text and "http://" not in page.text and "https://" not in page.text

    api = client.get("/orbitcrate/api/catalog")
    assert api.status_code == 502 and api.json() == {"detail": "The demonstration application is not reachable."}
    assert api.headers["retry-after"] == str(store.RETRY_SECONDS)

    # As soon as the store answers, the same address shows the store.
    upstream.fail = False
    assert client.get("/orbitcrate/", headers={"Accept": "text/html"}).status_code == 200


def test_each_client_address_is_rate_limited(client, upstream, monkeypatch):
    monkeypatch.setattr(store, "requests_per_client", store.SlidingWindowLimiter(3, 60))
    codes = [client.get("/orbitcrate/api/catalog").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert len(upstream.calls) == 3
    refused = client.get("/orbitcrate/api/catalog")
    assert int(refused.headers["retry-after"]) >= 1


def test_path_check():
    assert store.is_allowed("")
    assert store.is_allowed("static/app.js")
    assert store.is_allowed("static/fonts/manrope-latin-wght-normal.woff2")
    assert store.is_allowed("api/orders/OC-ABC123/cancel")
    for bad in ("internal/state", "metrics", "health", "static", "api", "static/..", "api/./x", "api/a b", "x/y"):
        assert not store.is_allowed(bad), bad
