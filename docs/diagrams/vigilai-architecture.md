# VigilAI Architecture

VigilAI is a pipeline in `backend/app/assistant/service.py` in which the language model is only one step: scope validation, retrieval, live-data access and output checks are ordinary backend code that does not depend on the model following its instructions. When Gemini is not configured or a call fails, the same documentation and live data are returned directly (documentation fallback). Live Gemini generation was verified on 2026-11-23 with a real API key and the default model `gemini-3.5-flash-lite` by `scripts/verify_gemini_live.py` (evidence in [`../evidence/gemini-live.json`](../evidence/gemini-live.json)); real quota exhaustion (HTTP 429 from the provider) was not observed.

```mermaid
flowchart TD
    q(["POST /api/assistant/chat"]) --> auth{"Valid JWT and permission assistant:use?"}
    auth -->|"no"| e401["HTTP 401 or 403"]
    auth -->|"yes"| enabled{"Runtime setting assistant.enabled?"}
    enabled -->|"no"| off["Fixed reply: assistant turned off"]
    enabled -->|"yes"| rl{"Per-user rate limit, safeguard 9"}
    rl -->|"exceeded"| e429["HTTP 429 with Retry-After"]
    rl -->|"ok"| scope{"scope.classify, safeguards 1 and 6"}
    scope -->|"out of scope, action order, secret request or injection"| refuse["Fixed refusal text. Audit event unless plainly out of scope"]
    scope -->|"in scope"| kb["Knowledge-base retrieval: BM25 over knowledge_base Markdown, safeguard 2"]
    kb --> tools["Deterministic routing to read-only context tools: permission check per tool, clipped summaries, safeguards 3, 4 and 5"]
    tools --> found{"Any documentation or live data found?"}
    found -->|"no"| refuse2["Out-of-scope refusal"]
    found -->|"yes"| prov{"Gemini configured and daily budget left?"}
    prov -->|"no"| fb["Documentation fallback: notice, live data, top documentation sections"]
    prov -->|"yes"| gem["Gemini generate_content: system instruction plus delimited and escaped context"]
    gem -->|"error, timeout, quota or empty answer"| fb
    gem -->|"text"| val["validate_reply: sentinel, action claims, markup, secrets, length, safeguards 7 and 8"]
    fb --> strip["strip_secrets, safeguard 8"]
    val --> replyAi(["JSON reply, mode ai or refusal"])
    strip --> replyFb(["JSON reply, mode fallback with notice"])
    replyAi --> ui["Browser: SafeText renders text nodes, never HTML"]
    replyFb --> ui
    off --> ui
    refuse --> ui
    refuse2 --> ui
```

The numbered safeguards are mapped to modules and functions in [../security.md](../security.md#vigilai-safeguards).
