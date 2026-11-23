"""Backend scope validation for VigilAI (safeguard layer 1).

This runs *before* any documentation retrieval, live-data access or model
call, and does not depend on the model obeying its system prompt.  It decides
whether a message is:

* IN_SCOPE          - a question about VigilOps / its integrated services
* OUT_OF_SCOPE      - anything else (general knowledge, creative writing, ...)
* PRIVILEGED_ACTION - an instruction to *do* something (approve, execute, delete ...)
* SECRET_REQUEST    - an attempt to obtain credentials or keys
* PROMPT_INJECTION  - an attempt to change the assistant's rules or role
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import List, Sequence


class Scope(str, enum.Enum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    PRIVILEGED_ACTION = "privileged_action"
    SECRET_REQUEST = "secret_request"
    PROMPT_INJECTION = "prompt_injection"


@dataclass
class ScopeResult:
    scope: Scope
    reason: str
    score: int = 0
    matched: List[str] = field(default_factory=list)
    follow_up: bool = False

    @property
    def allowed(self) -> bool:
        return self.scope is Scope.IN_SCOPE


# --- prompt injection -------------------------------------------------------
_INJECTION = re.compile(
    r"(ignore|disregard|forget|override|bypass)\s+(all\s+|any\s+|the\s+|your\s+|my\s+|these\s+|those\s+)*"
    r"(previous|prior|above|earlier|preceding|system|initial|original)?\s*"
    r"(instruction|rule|prompt|guideline|restriction|polic|safeguard|constraint)"
    r"|\byou\s+are\s+now\b|\bfrom\s+now\s+on\s+you\b|\bact\s+as\b|\bpretend\s+(to\s+be|you\s+are|that)\b"
    r"|\brole\s*-?\s*play\b|\bsystem\s+prompt\b|\bdeveloper\s+mode\b|\bjailbreak\b|\bdan\s+mode\b"
    r"|\b(reveal|show|print|repeat|output)\s+(me\s+)?(your|the)\s+(instructions|prompt|rules|guidelines)\b"
    r"|\bnew\s+instructions?\s*:"
    r"|\b(no|without)\s+(any\s+)?restrictions\b",
    re.IGNORECASE,
)

# --- secrets ----------------------------------------------------------------
_SECRET_NOUN = (
    r"(api[\s_-]?keys?|secret[\s_-]?keys?|secrets?|passwords?|passwd|credentials?|"
    r"(access|auth|bearer|jwt|webhook|recovery|control)[\s_-]?tokens?|tokens?|private[\s_-]?keys?|"
    r"connection[\s_-]?strings?|\.env|env(ironment)?\s+(file|variables?|vars?)|database[\s_-]?url|"
    r"password[\s_-]?hash(es)?)"
)
_REVEAL_VERB = (
    r"(reveal|show|give|tell|print|display|leak|dump|share|send|expose|output|read|list|fetch|"
    r"get|provide|what\s+is|what's|whats|what\s+are)"
)
# "password policy", "token expiry" etc. are about behaviour, not about a secret value.
_NOT_A_VALUE = (
    r"(?!\s+(polic|requirement|rule|length|expir|lifetime|rotation|hashing|strength|reset|"
    r"complexity|validation|handling|storage|management|field|limit))"
)
_SECRET_REQUEST = re.compile(
    rf"\b{_REVEAL_VERB}\b[^?!\n]{{0,60}}?(?<![A-Za-z0-9]){_SECRET_NOUN}(?![A-Za-z0-9]){_NOT_A_VALUE}",
    re.IGNORECASE,
)
# Questions about *how to configure* a secret are legitimate platform questions.
_SECRET_HOWTO = re.compile(
    r"\b(how\s+(do|can|should|to)|where\s+(do|can|should|to)|steps?\s+to|guide\s+to)\b[^.?!\n]{0,40}"
    r"\b(set|configure|add|rotate|change|generate|create|store|provide|obtain|update|supply|put)\b",
    re.IGNORECASE,
)

# --- privileged / state-changing instructions --------------------------------
_ACTION_VERBS = (
    "approve|reject|deny|execute|run|trigger|launch|start|stop|delete|remove|erase|drop|close|"
    "resolve|acknowledge|ack|reopen|change|update|modify|edit|set|disable|enable|create|add|"
    "reset|restart|reboot|recover|fix|remediate|patch|grant|revoke|promote|demote|make|inject|"
    "cancel|retry|deploy|kill|shutdown|shut\\s+down|scan|rescan|assign|escalate|dispatch|queue|"
    "purge|wipe|rotate|rollback|roll\\s+back|turn\\s+(on|off)|switch\\s+(on|off)"
)
_POLITE = (
    r"(?:(?:please|kindly|now|just|ok(?:ay)?|hey|hi|vigilai|then|and|so)[\s,]+|"
    r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
    r"i\s+(?:want|need|would\s+like)\s+you\s+to\s+|i\s+order\s+you\s+to\s+|you\s+(?:must|should|need\s+to)\s+|"
    r"go\s+ahead\s+and\s+)*"
)
_IMPERATIVE = re.compile(rf"^\s*{_POLITE}(?P<verb>{_ACTION_VERBS})\b", re.IGNORECASE)
_DO_IT_FOR_ME = re.compile(
    rf"\b({_ACTION_VERBS})\b[^.?!\n]{{0,80}}\b(for\s+me|on\s+my\s+behalf|right\s+now|immediately|yourself)\b",
    re.IGNORECASE,
)
_SHELL = re.compile(
    r"\b(sudo|bash|powershell|cmd\.exe|rm\s+-rf|chmod|curl\s+http|wget\s+http|docker\s+(exec|run|rm|stop|kill)|"
    r"kubectl|drop\s+table|delete\s+from|shell\s+command|run\s+(a\s+|the\s+|this\s+)?(command|script|query|sql))\b",
    re.IGNORECASE,
)
# Phrasings that ask *about* an action rather than ordering it.
_INFORMATIONAL = re.compile(
    r"^\s*(how|what|why|when|where|who|which|whom|whose|is|are|was|were|does|do|did|"
    r"should|explain|describe|tell\s+me\s+(about|how|what|why)|show\s+me\s+how|"
    r"can\s+(i|we|an?|the|operators?|admin\w*)|could\s+(i|we)|may\s+i|am\s+i)\b",
    re.IGNORECASE,
)

# --- task types that are never platform support ------------------------------
_OFF_TOPIC_TASK = re.compile(
    r"\b(poem|poetry|haiku|limerick|sonnet|joke|riddle|pun|story|tale|novel|song|lyrics|rap|essay|"
    r"recipe|horoscope|zodiac|fortune|trivia|quiz\s+me|fun\s+fact|general\s+knowledge|"
    r"stock\s+(market|price|tip|prediction)|crypto(currency)?|bitcoin|lottery|bet(ting)?|"
    r"weather|movie|film|cricket|football|celebrity|prime\s+minister|president\s+of|capital\s+of|"
    r"homework|translate\s+(this|to|into)|love\s+letter|dating)\b",
    re.IGNORECASE,
)

# --- domain vocabulary --------------------------------------------------------
_STRONG_TERMS = [
    r"vigil\s?ops", r"vigil\s?ai", r"incidents?", r"alerts?", r"alerting", r"alert\s?manager",
    r"prometheus", r"promql", r"remediat\w*", r"findings?", r"sec-?00[1-5]", r"security\s+(rule|scan|finding|posture)\w*",
    r"scans?", r"scanner", r"scanning", r"audit\w*", r"dashboard", r"monitor\w*", r"metrics?", r"telemetry",
    r"uptime", r"latency", r"error\s+rate", r"[45]xx", r"http\s*[45]\d\d", r"\b50[0234]\s+errors?",
    r"health\s*(check|probe|endpoint|status)?s?", r"unhealthy", r"outage", r"downtime", r"unavailable",
    r"operators?", r"administrators?", r"admins?", r"rbac", r"permissions?", r"roles?", r"approv\w*",
    r"webhook", r"docker\s+compose", r"compose\.ya?ml", r"public\s+(storage|access|bucket)", r"buckets?",
    r"encrypt\w*", r"iam", r"wildcards?", r"inbound", r"ingress", r"security\s+groups?",
    r"privileged", r"misconfigur\w*", r"ya?ml", r"action-?00[12]", r"worker", r"recover\w*",
    r"dedup\w*", r"fingerprint", r"gemini", r"knowledge\s+base", r"demo\s+(app|application|controls?|environment)",
    r"fault\s+injection", r"scrape\w*", r"targets?", r"postgres\w*", r"caddy", r"reverse\s+proxy",
    r"verification", r"verif(y|ied)", r"accepted\s+risk", r"lifecycle", r"acknowledg\w*", r"severity",
    r"request\s+rate", r"rate\s+limit\w*", r"sign\s?(in|out)", r"log\s?(in|out)", r"session", r"platform",
    r"runbook", r"troubleshoot\w*", r"backup", r"restore", r"migrations?", r"alembic", r"deployment",
    r"password\s+(policy|requirements?|rules?|reset)", r"two\s+roles", r"user\s+management",
]
_WEAK_TERMS = [
    r"applications?", r"apps?", r"services?", r"servers?", r"cpu", r"memory", r"errors?", r"slow",
    r"down", r"healthy", r"status", r"api", r"config\w*", r"security", r"logs?", r"users?", r"ports?",
    r"containers?", r"storage", r"network", r"cloud", r"deploy\w*", r"docker", r"database", r"backend",
    r"frontend", r"install\w*", r"setup", r"settings?", r"password", r"account", r"requests?", r"pending",
    r"open", r"resolved?", r"failed", r"failure", r"critical", r"https?", r"tls", r"environment",
]
_STRONG = [(re.compile(rf"\b{p}\b", re.IGNORECASE), p) for p in _STRONG_TERMS]
_WEAK = [(re.compile(rf"\b{p}\b", re.IGNORECASE), p) for p in _WEAK_TERMS]

_FOLLOW_UP = re.compile(
    r"\b(it|its|that|this|these|those|them|they|the\s+same|what\s+about|and\s+then|next|more|"
    r"elaborate|details?|example|steps?|why|how|mean(s|t)?|happen(s|ed)?|again|else|first\s+one|"
    r"second\s+one|last\s+one|continue|go\s+on)\b",
    re.IGNORECASE,
)

IN_SCOPE_THRESHOLD = 2
_MAX_FOLLOW_UP_WORDS = 14


def normalise(text: str) -> str:
    """Collapse whitespace and drop control characters."""
    cleaned = "".join(ch if ch.isprintable() or ch in "\n\t" else " " for ch in text)
    return re.sub(r"\s+", " ", cleaned).strip()


def relevance(text: str) -> tuple[int, List[str]]:
    score = 0
    matched: List[str] = []
    for pattern, label in _STRONG:
        if pattern.search(text):
            score += 2
            matched.append(label)
    for pattern, label in _WEAK:
        if pattern.search(text):
            score += 1
            matched.append(label)
    return score, matched


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def is_action_instruction(text: str) -> bool:
    if _SHELL.search(text):
        return True
    if _INFORMATIONAL.match(text):
        return bool(_DO_IT_FOR_ME.search(text))
    return bool(_IMPERATIVE.match(text) or _DO_IT_FOR_ME.search(text))


def classify(message: str, previous_user_messages: Sequence[str] = ()) -> ScopeResult:
    text = normalise(message)
    if not text:
        return ScopeResult(Scope.OUT_OF_SCOPE, "empty message")

    if _INJECTION.search(text):
        return ScopeResult(Scope.PROMPT_INJECTION, "instruction-override pattern")

    if _SECRET_REQUEST.search(text) and not _SECRET_HOWTO.search(text):
        return ScopeResult(Scope.SECRET_REQUEST, "credential disclosure request")

    if _OFF_TOPIC_TASK.search(text):
        return ScopeResult(Scope.OUT_OF_SCOPE, "off-topic task type")

    score, matched = relevance(text)

    if is_action_instruction(text):
        # Ordering the assistant to act is refused whether or not it names a
        # platform object; unrelated orders are simply out of scope.
        if score >= IN_SCOPE_THRESHOLD or _SHELL.search(text):
            return ScopeResult(Scope.PRIVILEGED_ACTION, "state-changing instruction", score, matched)

    if score >= IN_SCOPE_THRESHOLD:
        return ScopeResult(Scope.IN_SCOPE, "platform vocabulary", score, matched)

    # Short follow-ups ("why did that happen?") inherit the scope of the conversation.
    if previous_user_messages and len(text.split()) <= _MAX_FOLLOW_UP_WORDS and _FOLLOW_UP.search(text):
        last = normalise(previous_user_messages[-1])
        last_score, _ = relevance(last)
        if last_score >= IN_SCOPE_THRESHOLD and not _OFF_TOPIC_TASK.search(last):
            return ScopeResult(Scope.IN_SCOPE, "follow-up to an in-scope question", score, matched, follow_up=True)

    return ScopeResult(Scope.OUT_OF_SCOPE, "no platform-related content", score, matched)
