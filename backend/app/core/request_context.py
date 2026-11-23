"""Per-request context (correlation id, client address) stored in contextvars."""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_client_ip: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)



def new_request_id(inbound: Optional[str] = None) -> str:
    """Mint a fresh request id.

    A caller-supplied X-Request-ID is deliberately NOT adopted: the request id
    becomes the audit correlation id, so accepting one would let a client file
    its own events under another workflow's correlation id.
    """
    return str(uuid.uuid4())


def set_request_context(request_id: str, client_ip: Optional[str]) -> None:
    _request_id.set(request_id)
    _client_ip.set(client_ip)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def get_client_ip() -> Optional[str]:
    return _client_ip.get()
