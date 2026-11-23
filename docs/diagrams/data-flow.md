# Data Flow Diagram (Level 1)

The diagram shows the eight main processes, the four data stores and the external entities. Every state-changing process writes its audit events through the same process (7) into the operational database, in the same transaction as the change itself.

```mermaid
flowchart LR
    user["User: Administrator or Operator"]
    demoapp["Demo application"]
    gemini["Google Gemini API"]

    p1(["1 Authenticate and authorise"])
    p2(["2 Query monitoring data"])
    p3(["3 Ingest alerts and manage incidents"])
    p4(["4 Scan configuration files"])
    p5(["5 Manage remediation requests"])
    p6(["6 Execute and verify remediation (worker)"])
    p7(["7 Record audit events"])
    p8(["8 Answer VigilAI questions"])

    d1[("D1 PostgreSQL operational database")]
    d2[("D2 Prometheus time series and alert state")]
    d3[("D3 Scan workspace YAML files")]
    d4[("D4 Knowledge base Markdown files")]

    user -->|"e-mail and password"| p1
    p1 -->|"JWT and permission list"| user
    d1 -->|"users, revoked tokens"| p1

    demoapp -->|"metrics scraped every 5 s"| d2
    d2 -->|"samples, targets, alert state"| p2
    p2 -->|"metric cards and charts"| user

    d2 -->|"firing and resolved alerts via Alertmanager webhook"| p3
    user -->|"status changes and comments"| p3
    p3 -->|"incidents and timeline events"| d1
    p3 -->|"incident list and detail"| user

    user -->|"scan request"| p4
    d3 -->|"YAML content"| p4
    p4 -->|"scan history and findings"| d1

    user -->|"request, approve, reject, dispatch, retry, cancel"| p5
    p5 -->|"request state up to QUEUED"| d1
    d1 -->|"queued requests"| p6
    p6 -->|"recovery call"| demoapp
    p6 -->|"corrected file"| d3
    d2 -->|"verification evidence"| p6
    d3 -->|"corrected file for the verification scan"| p6
    p6 -->|"executions, verification results, resolved incident"| d1

    user -->|"question and recent turns"| p8
    d4 -->|"matching sections"| p8
    d1 -->|"role-filtered summaries"| p8
    d2 -->|"monitoring summary"| p8
    p8 -->|"prompt with minimised context"| gemini
    gemini -->|"generated text"| p8
    p8 -->|"validated, sanitised reply"| user

    p1 --> p7
    p3 --> p7
    p4 --> p7
    p5 --> p7
    p6 --> p7
    p8 --> p7
    p7 -->|"append-only audit events"| d1
    d1 -->|"audit events filtered by role"| user
```
