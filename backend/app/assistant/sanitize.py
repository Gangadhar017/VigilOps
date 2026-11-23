"""Response validation and output sanitisation for VigilAI (safeguard layers 7-8).

Model output is treated as untrusted text.  Before it reaches the browser it is
checked for the out-of-scope sentinel, for claims of having performed an
action, and for anything resembling a secret; markup is stripped and the length
is bounded.  The frontend additionally renders replies as text, never as HTML.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from app.assistant.prompts import OUT_OF_SCOPE_REPLY, READ_ONLY_REPLY, SENTINEL_OUT_OF_SCOPE
from app.core.config import settings
from app.core.logging import redact

MAX_REPLY_CHARS = 4000

_HTML_TAG = re.compile(r"</?[A-Za-z][^<>]{0,200}>")
_SCRIPTY = re.compile(r"(?i)javascript:|data:text/html|on(error|load|click)\s*=")
_ACTION_CLAIM = re.compile(
    r"(?i)\bI(?:'ve|\s+have|\s+just|\s+have\s+just|\s+went\s+ahead\s+and)?\s+"
    r"(approved|rejected|executed|ran|run|triggered|deleted|removed|changed|updated|modified|"
    r"restarted|recovered|resolved|closed|acknowledged|fixed|remediated|enabled|disabled|created|"
    r"reset|queued|dispatched|cancelled|canceled|granted|revoked)\b"
)
_NEGATED = re.compile(r"(?i)\bI\s+(can(?:'|no)t|cannot|am\s+not\s+able|am\s+unable|do\s+not|don't|won't|will\s+not)\b")


@dataclass
class ValidatedReply:
    text: str
    out_of_scope: bool = False
    replaced: bool = False
    notes: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


def _configured_secrets() -> List[str]:
    candidates = [
        settings.SECRET_KEY,
        settings.GEMINI_API_KEY,
        settings.ALERT_WEBHOOK_TOKEN,
        settings.DEMO_APP_CONTROL_TOKEN,
        settings.DEMO_APP_RECOVERY_TOKEN,
        settings.BOOTSTRAP_ADMIN_PASSWORD,
        settings.BOOTSTRAP_OPERATOR_PASSWORD,
    ]
    # The database password sits between ':' and '@' in the connection URL.
    match = re.search(r"://[^:/@]+:([^@]+)@", settings.DATABASE_URL)
    if match:
        candidates.append(match.group(1))
    return [value for value in candidates if value and len(value) >= 6]


def strip_secrets(text: str) -> str:
    for secret in _configured_secrets():
        if secret in text:
            text = text.replace(secret, "[REDACTED]")
    return redact(text)


def validate_reply(raw: str) -> ValidatedReply:
    text = (raw or "").strip()
    notes: List[str] = []

    # The model signalled that the question is outside the platform's scope.
    if SENTINEL_OUT_OF_SCOPE in text[:200] or text.upper().strip(" .`*\"'") == SENTINEL_OUT_OF_SCOPE:
        return ValidatedReply(OUT_OF_SCOPE_REPLY, out_of_scope=True, replaced=True, notes=["sentinel"])

    cleaned = _HTML_TAG.sub("", text)
    cleaned = _SCRIPTY.sub("", cleaned)
    if cleaned != text:
        notes.append("markup_removed")

    redacted = strip_secrets(cleaned)
    if redacted != cleaned:
        notes.append("secret_redacted")
    cleaned = redacted

    # A read-only assistant must never claim to have changed anything.
    for sentence in re.split(r"(?<=[.!?\n])\s+", cleaned):
        if _ACTION_CLAIM.search(sentence) and not _NEGATED.search(sentence):
            return ValidatedReply(READ_ONLY_REPLY, replaced=True, notes=notes + ["action_claim"])

    if len(cleaned) > MAX_REPLY_CHARS:
        cleaned = cleaned[:MAX_REPLY_CHARS].rsplit(" ", 1)[0] + " …"
        notes.append("truncated")

    return ValidatedReply(cleaned.strip(), notes=notes)
