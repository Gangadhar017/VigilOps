"""VigilAI request pipeline.

    message
      -> input limits + per-user rate limit            (safeguard 9)
      -> backend scope validation                      (safeguard 1, 6)
      -> restricted documentation retrieval            (safeguard 2)
      -> authorised read-only live-data functions      (safeguards 3, 4, 5)
      -> Gemini (if configured and within budget)
      -> response validation + output sanitisation     (safeguards 7, 8)
      -> reply

If Gemini is not configured, fails, times out or runs out of quota, the same
documentation and live data are returned directly (documentation fallback) and
the user is told that live AI generation is temporarily unavailable.  Nothing
in this module can change platform state.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.assistant import context_tools
from app.assistant.prompts import (
    DISABLED_REPLY,
    INJECTION_REPLY,
    OUT_OF_SCOPE_REPLY,
    READ_ONLY_REPLY,
    SECRET_REPLY,
    SUGGESTED_QUESTIONS,
    SYSTEM_INSTRUCTION,
    WELCOME_MESSAGE,
    build_prompt,
)
from app.assistant.providers import FALLBACK_NOTICES, ProviderError, get_provider
from app.assistant.retrieval import Chunk, get_knowledge_base
from app.assistant.sanitize import strip_secrets, validate_reply
from app.assistant.scope import Scope, classify, looks_like_injection, normalise
from app.core.config import settings
from app.core.metrics import ASSISTANT_PROVIDER_LATENCY, ASSISTANT_REQUESTS
from app.core.rate_limit import SlidingWindowLimiter
from app.models.models import AuditOutcome, User
from app.services.audit_service import record_audit
from app.services.settings_service import get_setting

logger = logging.getLogger("vigilops.assistant")

_user_limiter = SlidingWindowLimiter(settings.AI_RATE_LIMIT_PER_MINUTE, 60)

_daily_lock = threading.Lock()
_daily_day: Optional[date] = None
_daily_count = 0


# The last in-scope question of each user, remembered on the server.  Whether a
# short follow-up ("how do I fix it?") is in scope is decided from THIS, never
# from the conversation history the browser sends, which could be fabricated.
FOLLOW_UP_TTL_SECONDS = 900
_last_in_scope: Dict[int, Tuple[float, str]] = {}
_last_in_scope_lock = threading.Lock()


def _recall_in_scope(user_id: int) -> List[str]:
    with _last_in_scope_lock:
        entry = _last_in_scope.get(user_id)
        if entry and time.monotonic() - entry[0] <= FOLLOW_UP_TTL_SECONDS:
            return [entry[1]]
        _last_in_scope.pop(user_id, None)
        return []


def _remember_in_scope(user_id: int, question: str) -> None:
    with _last_in_scope_lock:
        if len(_last_in_scope) > 5000:  # bounded memory
            _last_in_scope.clear()
        _last_in_scope[user_id] = (time.monotonic(), question)


class AssistantRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


def reset_limits() -> None:
    """Clear in-memory counters (used by tests)."""
    global _daily_day, _daily_count
    _user_limiter.clear()
    with _daily_lock:
        _daily_day, _daily_count = None, 0
    with _last_in_scope_lock:
        _last_in_scope.clear()


def _consume_daily_budget() -> bool:
    """Protect the provider's free quota with a server-wide daily cap."""
    global _daily_day, _daily_count
    if settings.AI_DAILY_REQUEST_LIMIT <= 0:
        return True
    today = datetime.now(timezone.utc).date()
    with _daily_lock:
        if _daily_day != today:
            _daily_day, _daily_count = today, 0
        if _daily_count >= settings.AI_DAILY_REQUEST_LIMIT:
            return False
        _daily_count += 1
        return True


def status(db: Session) -> Dict[str, Any]:
    enabled = bool(get_setting(db, "assistant.enabled"))
    knowledge_base = get_knowledge_base()
    return {
        "enabled": enabled,
        "provider": settings.AI_PROVIDER,
        "model": settings.GEMINI_MODEL if settings.AI_PROVIDER == "gemini" else None,
        "live_ai_configured": settings.ai_configured,
        "mode": "ai" if (enabled and settings.ai_configured) else "documentation",
        "welcome_message": WELCOME_MESSAGE,
        "suggested_questions": SUGGESTED_QUESTIONS,
        "knowledge_base_topics": knowledge_base.topics(),
        "max_input_chars": settings.AI_MAX_INPUT_CHARS,
        "capabilities": {"read_only": True, "can_execute_actions": False},
    }


# ---------------------------------------------------------------------------
# Fallback rendering (documentation + live data, no model)
# ---------------------------------------------------------------------------
def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}: {_format_value(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, list):
        return "; ".join(_format_value(v) for v in value) if value else "none"
    return str(value)


def render_live_data(tool_results: List[Dict[str, Any]]) -> str:
    """Readable bullet summary of retrieved live data."""
    lines: List[str] = []
    for result in tool_results:
        tool = result.get("tool", "live_data")
        data = result.get("data")
        if result.get("denied"):
            lines.append(f"- {tool}: your role is not permitted to view this information.")
            continue
        if result.get("error"):
            lines.append(f"- {tool}: {result['error']}")
            continue
        if not isinstance(data, dict):
            lines.append(f"- {tool}: {data}")
            continue

        if tool == "get_authorized_open_incidents":
            lines.append(f"- Open incidents: {data['open_incident_count']}")
            for item in data["incidents"]:
                firing = "alert still firing" if item["alert_still_firing"] else "alert cleared"
                lines.append(
                    f"  - #{item['id']} [{item['severity']}/{item['status']}] {item['title']} "
                    f"(resource: {item['resource']}, {firing})"
                )
        elif tool == "get_authorized_security_findings":
            lines.append(f"- Unresolved security findings: {data['unresolved_finding_count']}")
            for item in data["findings"]:
                lines.append(
                    f"  - #{item['id']} {item['rule']} {item['rule_name']} [{item['severity']}/{item['status']}] "
                    f"on {item['resource']} in {item['file']}"
                )
        elif tool == "get_authorized_remediation_requests":
            lines.append(f"- Matching remediation requests: {data['matching_request_count']}")
            for item in data["requests"]:
                lines.append(
                    f"  - #{item['id']} {item['action']} -> {item['status']} (target: {item['target']}, "
                    f"requested by {item['requested_by']})"
                )
        elif tool == "get_monitoring_summary":
            prom = "available" if data["prometheus_available"] else f"UNAVAILABLE ({data.get('prometheus_error')})"
            lines.append(f"- Prometheus: {prom}; Alertmanager: {'available' if data['alertmanager_available'] else 'UNAVAILABLE'}")
            for target in data["scrape_targets"]:
                extra = f" - {target['last_error']}" if target.get("last_error") else ""
                lines.append(f"  - scrape target {target['job']}: {target['health']}{extra}")
            for alert in data["firing_alerts"]:
                lines.append(f"  - alert {alert['name']} is {alert['state']} ({alert['severity']}) on {alert['resource']}")
            for resource in data["monitored_resources"]:
                available = {
                    key: f"{metric['value']} {metric['unit']}"
                    for key, metric in resource["metrics"].items()
                    if metric.get("value") is not None
                }
                detail = f" ({_format_value(available)})" if available else ""
                lines.append(f"  - {resource['name']}: {resource['status']}{detail}")
        else:
            lines.append(f"- {tool}: {_format_value(data)}")
    return "\n".join(lines)


def compose_fallback(
    chunks: Sequence[Tuple[Chunk, float]],
    tool_results: List[Dict[str, Any]],
) -> str:
    # The notice itself travels in the response's "notice" field and is shown separately.
    parts = ["Here is what the VigilOps documentation and live platform data say:"]
    if tool_results:
        retrieved = tool_results[0].get("retrieved_at", "")
        parts.append(f"Live platform data (retrieved {retrieved} UTC):\n{render_live_data(tool_results)}")
    for chunk, _score in list(chunks)[:2]:
        text = chunk.text.strip()
        if len(text) > 900:
            text = text[:900].rsplit(" ", 1)[0] + " …"
        parts.append(f"From the documentation - {chunk.reference}:\n{text}")
    if not chunks and not tool_results:
        parts.append(
            "I could not find anything about that in the VigilOps knowledge base. Try asking about "
            "monitoring, incidents, security rules (SEC-001 to SEC-005), remediation or user roles."
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def _clean_history(history: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """History comes from the browser and is therefore untrusted and bounded."""
    cleaned: List[Dict[str, str]] = []
    for turn in list(history)[-settings.AI_MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = normalise(str(turn.get("content", "")))[:600]
        # Turns that try to override the assistant's rules are dropped, not forwarded.
        if role in ("user", "assistant") and content and not looks_like_injection(content):
            cleaned.append({"role": role, "content": content})
    return cleaned


def _reply(
    text: str,
    *,
    mode: str,
    scope: Scope,
    chunks: Sequence[Tuple[Chunk, float]] = (),
    tool_results: Sequence[Dict[str, Any]] = (),
    notice: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    ASSISTANT_REQUESTS.labels(outcome=mode).inc()
    return {
        "reply": text,
        "mode": mode,  # ai | fallback | refusal
        "scope": scope.value,
        "notice": notice,
        "provider": provider,
        "model": model,
        "sources": [
            {"document": chunk.document, "title": chunk.title, "section": chunk.section}
            for chunk, _score in chunks
        ],
        "live_data": [
            {
                "tool": result.get("tool"),
                "retrieved_at": result.get("retrieved_at"),
                "denied": bool(result.get("denied")),
            }
            for result in tool_results
        ],
    }


def chat(db: Session, user: User, message: str, history: Sequence[Dict[str, str]] = ()) -> Dict[str, Any]:
    started = time.monotonic()
    question = normalise(message)[: settings.AI_MAX_INPUT_CHARS]

    if not get_setting(db, "assistant.enabled"):
        return _reply(DISABLED_REPLY, mode="refusal", scope=Scope.OUT_OF_SCOPE)

    allowed, retry_after = _user_limiter.allow(f"user:{user.id}")
    if not allowed:
        ASSISTANT_REQUESTS.labels(outcome="rate_limited").inc()
        raise AssistantRateLimited(retry_after)

    clean_history = _clean_history(history)
    previous_user = _recall_in_scope(user.id)
    decision = classify(question, previous_user)

    if not decision.allowed:
        refusals = {
            Scope.OUT_OF_SCOPE: OUT_OF_SCOPE_REPLY,
            Scope.PRIVILEGED_ACTION: READ_ONLY_REPLY,
            Scope.SECRET_REQUEST: SECRET_REPLY,
            Scope.PROMPT_INJECTION: INJECTION_REPLY,
        }
        if decision.scope is not Scope.OUT_OF_SCOPE:
            # Security-relevant: attempts to make the assistant act, leak or change its rules.
            record_audit(
                db,
                action="ASSISTANT_REQUEST_BLOCKED",
                entity_type="assistant",
                actor=user,
                outcome=AuditOutcome.DENIED,
                metadata={"category": decision.scope.value, "reason": decision.reason},
            )
            db.commit()
        logger.info(
            "assistant request refused",
            extra={"user_id": user.id, "scope": decision.scope.value, "chars": len(question)},
        )
        return _reply(refusals[decision.scope], mode="refusal", scope=decision.scope)

    # Follow-ups are retrieved together with the question they refer to.
    retrieval_query = question
    if decision.follow_up and previous_user:
        retrieval_query = f"{previous_user[-1]} {question}"
        _remember_in_scope(user.id, previous_user[-1])  # keep the anchor, refresh its age
    else:
        _remember_in_scope(user.id, question)

    chunks = get_knowledge_base().search(retrieval_query, limit=4)
    tool_calls = context_tools.select_tools(retrieval_query)
    tool_results = context_tools.run_tools(db, user, tool_calls)

    if not chunks and not tool_results:
        # Passed the vocabulary check but nothing in the platform's knowledge matches.
        return _reply(OUT_OF_SCOPE_REPLY, mode="refusal", scope=Scope.OUT_OF_SCOPE)

    provider = get_provider()
    failure_kind: Optional[str] = None
    if provider is None:
        failure_kind = "not_configured"
    elif not _consume_daily_budget():
        failure_kind = "daily_limit"
    else:
        prompt = build_prompt(
            question=question,
            role=user.role,
            chunks=chunks,
            tool_results=tool_results,
            history=clean_history,
        )
        provider_started = time.monotonic()
        try:
            response = provider.generate(SYSTEM_INSTRUCTION, prompt)
            ASSISTANT_PROVIDER_LATENCY.observe(time.monotonic() - provider_started)
            validated = validate_reply(response.text)
            if validated.text:
                # Usage is logged without the question or the answer text.
                logger.info(
                    "assistant answered",
                    extra={
                        "user_id": user.id,
                        "mode": "ai",
                        "model": response.model,
                        "prompt_chars": len(prompt),
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "kb_chunks": len(chunks),
                        "tools": [r.get("tool") for r in tool_results],
                        "validation": validated.notes,
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    },
                )
                if validated.out_of_scope:
                    return _reply(validated.text, mode="refusal", scope=Scope.OUT_OF_SCOPE)
                return _reply(
                    validated.text,
                    mode="ai",
                    scope=Scope.IN_SCOPE,
                    chunks=chunks,
                    tool_results=tool_results,
                    provider=provider.name,
                    model=response.model,
                )
            failure_kind = "empty"
        except ProviderError as exc:
            ASSISTANT_PROVIDER_LATENCY.observe(time.monotonic() - provider_started)
            failure_kind = exc.kind
            logger.warning(
                "assistant provider failure",
                extra={"user_id": user.id, "kind": exc.kind, "detail": str(exc)[:200]},
            )
        except Exception as exc:  # noqa: BLE001 - the platform must keep working
            failure_kind = "unavailable"
            logger.exception("assistant provider error", extra={"error": exc.__class__.__name__})

    notice = FALLBACK_NOTICES.get(failure_kind or "unavailable", FALLBACK_NOTICES["unavailable"])
    text = strip_secrets(compose_fallback(chunks, tool_results))
    logger.info(
        "assistant answered",
        extra={
            "user_id": user.id,
            "mode": "fallback",
            "reason": failure_kind,
            "kb_chunks": len(chunks),
            "tools": [r.get("tool") for r in tool_results],
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
    )
    return _reply(
        text,
        mode="fallback",
        scope=Scope.IN_SCOPE,
        chunks=chunks,
        tool_results=tool_results,
        notice=notice,
        provider=provider.name if provider else None,
    )
