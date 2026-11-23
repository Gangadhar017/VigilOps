# Deployment Diagram

All long-running containers share one Docker bridge network (`internal`); the difference between the local stack (`compose.yaml`) and production (`compose.yaml` plus `compose.prod.yaml`) is which host ports are published. Locally the web application is published on port 8080 and three tool ports are bound to 127.0.0.1 only; the production overlay publishes nothing but 80 and 443 on `web`.

```mermaid
flowchart TB
    localUser["Local: browser on host port 8080"]
    localTools["Local only: 127.0.0.1 ports 8000, 9090 and 9093"]
    prodUser["Production: clients on host ports 80 and 443"]

    subgraph net["Docker bridge network: internal"]
        web["web: Caddy, container ports 80 and 443"]
        backend["backend: FastAPI on 8000, non-root uid 10001, one process"]
        worker["worker: no ports, read-only root filesystem, all capabilities dropped"]
        testapp["test-app: demo application on 8001, read-only root filesystem, 512 MB, 1 CPU"]
        postgres["postgres: PostgreSQL 16 on 5432"]
        prometheus["prometheus: v2.51.0 on 9090, 7 day retention"]
        alertmanager["alertmanager: v0.27.0 on 9093"]
    end

    init["workspace-init: one-shot, no network, sets volume ownership"]

    subgraph vols["Named volumes, bind mounts and secrets"]
        pgdata[("pgdata")]
        promdata[("prometheus_data")]
        amdata[("alertmanager_data")]
        workspace[("scan_workspace")]
        caddydata[("caddy_data and caddy_config")]
        monconf["monitoring/*.yml, bind mounted read-only"]
        secret["Compose secret alert_webhook_token, mounted as a file"]
    end

    localUser -->|"8080 to 80"| web
    prodUser -->|"80 and 443, TLS certificate obtained by Caddy"| web
    localTools -.->|"8000"| backend
    localTools -.->|"9090"| prometheus
    localTools -.->|"9093"| alertmanager

    web -->|"/api/* only"| backend
    backend --> postgres
    worker --> postgres
    backend --> prometheus
    worker --> prometheus
    worker --> testapp
    prometheus --> testapp
    prometheus --> backend
    prometheus --> alertmanager
    alertmanager -->|"webhook"| backend

    postgres --- pgdata
    prometheus --- promdata
    alertmanager --- amdata
    web --- caddydata
    backend ---|"read-only"| workspace
    worker ---|"read-write"| workspace
    init -->|"chown to uid 10001"| workspace
    monconf --- prometheus
    monconf --- alertmanager
    secret --- alertmanager
```

In production the overlay also sets `ENVIRONMENT=production` on the backend and the worker and forces `DEMO_CONTROLS_ENABLED=false` on the backend, the worker and the demo application. Step-by-step instructions are in [../deployment.md](../deployment.md).
