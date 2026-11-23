# Remediation Sequence

The API only records decisions and moves a request to QUEUED; the corrective action and its verification happen in the restricted worker, which claims queued rows from PostgreSQL. A request is SUCCEEDED only when verification with fresh evidence passes, otherwise it is FAILED and the underlying problem is treated as not fixed.

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator
    participant AD as Administrator
    participant API as API backend
    participant DB as PostgreSQL
    participant WK as Worker
    participant TG as Demo app or YAML file
    participant EV as Prometheus or Scanner

    OP->>API: POST /api/remediation/requests with source, action code and justification
    API->>DB: Check allowlist and applicability, insert request PENDING_APPROVAL, audit
    API-->>OP: 201 Created
    AD->>API: POST approve
    API->>DB: Check status and self-approval rule, set APPROVED, record approver, audit
    AD->>API: POST execute
    API->>DB: Set QUEUED, audit. The API performs no action itself
    loop Worker poll, every 2 seconds by default
        WK->>DB: Select the oldest QUEUED request FOR UPDATE SKIP LOCKED
    end
    WK->>DB: Refuse if no approver is recorded, otherwise set RUNNING and insert execution row
    WK->>TG: ACTION-001 calls POST /internal/recover, ACTION-002 edits the allowlisted file atomically
    TG-->>WK: Action result
    WK->>DB: Store execution details, set VERIFYING, audit
    WK->>TG: ACTION-001 only, readiness probes until three consecutive successes
    WK->>EV: ACTION-001 checks scrape target and alert state, ACTION-002 runs a new scan of the file
    EV-->>WK: Fresh evidence
    alt Every verification check passed
        WK->>DB: Set SUCCEEDED, resolve the incident with the evidence, audit
        Note over WK,DB: For ACTION-002 the finding was already set to RESOLVED by the verification scan
    else Action error, timeout or failed check
        WK->>DB: Set FAILED with the reason, finding back to OPEN, incident stays active, audit
        AD->>API: POST retry, allowed while attempts remain
        API->>DB: Set QUEUED again, audit
    end
    OP->>API: GET the remediation request
    API-->>OP: Status, executions, verification checks and audit timeline
```

Requests can also end as REJECTED (Administrator, with a reason) or CANCELLED (the requester or an Administrator, before dispatch); neither path reaches the worker.
