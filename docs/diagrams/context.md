# System Context Diagram

VigilOps sits between its two kinds of users, the workload it monitors and one external service. The Google Gemini API is the only dependency outside the deployment, it is called only by the backend, and the platform keeps working (documentation fallback) when it is not configured or not reachable.

```mermaid
flowchart TB
    admin["Administrator"]
    operator["Operator"]
    vigilops["VigilOps platform: web UI, API, restricted worker, PostgreSQL, Prometheus, Alertmanager"]
    demo["Monitored demo application (test-app)"]
    files["Authorised YAML configuration files (scan workspace)"]
    gemini["Google Gemini API (external)"]

    admin -->|"approves and dispatches remediation, administers users and settings"| vigilops
    operator -->|"monitors, investigates incidents, runs scans, requests remediation"| vigilops
    vigilops -->|"dashboards, incidents, findings, audit history, VigilAI answers"| admin
    vigilops -->|"dashboards, incidents, findings, operational audit history, VigilAI answers"| operator
    demo -->|"metrics and health state, scraped by Prometheus"| vigilops
    vigilops -->|"token-protected recovery call, ACTION-001"| demo
    files -->|"configuration read by the scanner"| vigilops
    vigilops -->|"correction of public storage access, ACTION-002"| files
    vigilops -->|"scope-checked question with minimised context"| gemini
    gemini -->|"generated text, validated before display"| vigilops
```

The scanner reads local files only: VigilOps is not connected to a cloud provider account.
