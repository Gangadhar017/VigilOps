# System Architecture

VigilOps runs as eight Docker Compose services on one private bridge network; `web` (Caddy) is the only service meant to be reached by users, and it forwards nothing but `/api/*` to the backend. The restricted worker has no inbound port: it only polls PostgreSQL for dispatched remediation requests and is the only writer of the scan workspace volume.

```mermaid
flowchart LR
    user["Administrator or Operator (browser)"]
    gemini["Google Gemini API"]

    subgraph host["Docker host: private bridge network named internal"]
        web["web: Caddy, serves the React build and proxies /api"]
        backend["backend: FastAPI API, incident engine, scanner, VigilAI"]
        worker["worker: restricted remediation worker, no ports"]
        db[("postgres: PostgreSQL 16")]
        prom["prometheus: scraping and alert rules"]
        am["alertmanager: grouping and routing"]
        app["test-app: monitored demo application"]
        ws[("scan_workspace volume: YAML files")]
    end

    user -->|"HTTP 8080 local, HTTPS 443 production"| web
    web -->|"/api/* only"| backend
    backend -->|"SQL"| db
    worker -->|"SQL: poll queue, store results"| db
    backend -->|"read-only HTTP queries"| prom
    backend -->|"readiness check"| am
    prom -->|"scrape /metrics"| app
    prom -->|"scrape /metrics"| backend
    prom -->|"firing alerts"| am
    am -->|"POST /api/alerts/webhook with bearer token"| backend
    backend -->|"read-only mount"| ws
    worker -->|"read-write mount"| ws
    worker -->|"POST /internal/recover with recovery token"| app
    worker -->|"verification queries"| prom
    backend -.->|"fault injection, demo mode only"| app
    backend -->|"HTTPS with server-side API key"| gemini
```

Not shown: the one-shot `workspace-init` container (it only sets the ownership of the `scan_workspace` volume and then exits, see [deployment.md](deployment.md)), and Prometheus scraping itself and Alertmanager.
