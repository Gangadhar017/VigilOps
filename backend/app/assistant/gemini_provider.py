"""Google Gemini provider (official Google Gen AI SDK, ``google-genai``).

The API key lives only in the backend's environment.  It is never sent to the
browser, never logged and never placed in a prompt.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.assistant.providers import ProviderError, ProviderResponse

logger = logging.getLogger(__name__)

_TRANSIENT_CODES = {500, 502, 503, 504}
# Google answers an invalid or expired key with HTTP 400 INVALID_ARGUMENT, not 401/403;
# the machine-readable reason is in the ErrorInfo detail (observed against the live API).
_KEY_REASONS = ("API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED")


def _is_key_problem(exc: Any) -> bool:
    details = getattr(exc, "details", None)
    entries = details.get("error", {}).get("details", []) if isinstance(details, dict) else []
    reasons = {str(entry.get("reason", "")) for entry in entries if isinstance(entry, dict)}
    if reasons & set(_KEY_REASONS):
        return True
    return "api key" in str(getattr(exc, "message", "") or "").lower()


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        client: Optional[Any] = None,
    ) -> None:
        from google import genai
        from google.genai import errors, types

        self.model = model
        self._types = types
        self._errors = errors
        self._max_output_tokens = max_output_tokens
        # The SDK timeout is expressed in milliseconds.  SDK-level retries are
        # disabled (attempts=1) so retry behaviour is controlled explicitly below.
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def _call(self, system_instruction: str, prompt: str) -> ProviderResponse:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=self._max_output_tokens,
            ),
        )
        try:
            text = response.text
        except Exception:  # noqa: BLE001 - e.g. the candidate has no text part
            text = None
        if not text or not text.strip():
            feedback = getattr(response, "prompt_feedback", None)
            if feedback is not None and getattr(feedback, "block_reason", None):
                raise ProviderError("blocked", "prompt blocked by provider safety settings")
            raise ProviderError("empty", "provider returned no text")
        usage = getattr(response, "usage_metadata", None)
        return ProviderResponse(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
        )

    def generate(self, system_instruction: str, prompt: str) -> ProviderResponse:
        last_error: Optional[ProviderError] = None
        for attempt in (1, 2):
            try:
                return self._call(system_instruction, prompt)
            except ProviderError:
                raise
            except self._errors.APIError as exc:
                code = getattr(exc, "code", None)
                status = str(getattr(exc, "status", "") or "")
                if code == 429 or "RESOURCE_EXHAUSTED" in status:
                    # Never retry quota errors: a retry only burns more quota.
                    raise ProviderError("rate_limited", f"HTTP {code} {status}") from exc
                if (
                    code in (401, 403)
                    or "PERMISSION_DENIED" in status
                    or "UNAUTHENTICATED" in status
                    or _is_key_problem(exc)
                ):
                    raise ProviderError("auth", f"HTTP {code} {status}") from exc
                if code in (400, 404):
                    raise ProviderError("invalid_request", f"HTTP {code} {status}") from exc
                last_error = ProviderError("unavailable", f"HTTP {code} {status}")
                if code in _TRANSIENT_CODES and attempt == 1:
                    time.sleep(1.0)  # one safe retry for a transient server error
                    continue
                raise last_error from exc
            except Exception as exc:  # noqa: BLE001 - network / timeout errors from the HTTP layer
                kind = "timeout" if "timeout" in exc.__class__.__name__.lower() else "unavailable"
                last_error = ProviderError(kind, exc.__class__.__name__)
                if kind == "unavailable" and attempt == 1:
                    time.sleep(0.5)
                    continue
                raise last_error from exc
        raise last_error or ProviderError("unavailable")
