"""AI provider abstraction.

The assistant service depends only on this small interface, so the model or
vendor can be changed through configuration (``AI_PROVIDER``, ``GEMINI_MODEL``)
without touching application logic.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional, Protocol

from app.core.config import settings


class ProviderError(RuntimeError):
    """A provider call failed.  ``kind`` drives the user-facing fallback notice."""

    KINDS = ("not_configured", "rate_limited", "timeout", "unavailable", "auth", "invalid_request", "blocked", "empty")

    def __init__(self, kind: str, message: str = "") -> None:
        super().__init__(message or kind)
        self.kind = kind if kind in self.KINDS else "unavailable"


@dataclass
class ProviderResponse:
    text: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class AIProvider(Protocol):
    name: str
    model: str

    def generate(self, system_instruction: str, prompt: str) -> ProviderResponse: ...


FALLBACK_NOTICES = {
    "not_configured": "Live AI generation is not configured on this server (no Gemini API key).",
    "rate_limited": "Live AI generation is temporarily unavailable because the AI provider's free quota or rate limit has been reached.",
    "timeout": "Live AI generation is temporarily unavailable because the AI provider did not respond in time.",
    "unavailable": "Live AI generation is temporarily unavailable because the AI provider could not be reached.",
    "auth": "Live AI generation is temporarily unavailable because the AI provider rejected the server's credentials.",
    "invalid_request": "Live AI generation is temporarily unavailable because the configured AI model rejected the request.",
    "blocked": "The AI provider declined to generate an answer for this request.",
    "empty": "The AI provider returned an empty answer.",
    "daily_limit": "Live AI generation is paused because this server's daily AI request budget has been used up.",
}

_provider: Optional[AIProvider] = None
_provider_built = False
_lock = threading.Lock()


def get_provider() -> Optional[AIProvider]:
    """Return the configured provider, or None when live AI is not available."""
    global _provider, _provider_built
    with _lock:
        if not _provider_built:
            _provider_built = True
            if settings.ai_configured:
                from app.assistant.gemini_provider import GeminiProvider

                _provider = GeminiProvider(
                    api_key=settings.GEMINI_API_KEY.strip(),
                    model=settings.GEMINI_MODEL,
                    timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                    max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                )
        return _provider


def set_provider(provider: Optional[AIProvider]) -> None:
    """Install a specific provider (used by tests)."""
    global _provider, _provider_built
    with _lock:
        _provider = provider
        _provider_built = True


def reset_provider() -> None:
    global _provider, _provider_built
    with _lock:
        _provider = None
        _provider_built = False
