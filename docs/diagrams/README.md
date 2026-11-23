# VigilOps Diagrams

Each file in this folder contains one Mermaid diagram that GitHub renders directly. The diagrams were drawn from the source code (the files named in the last column), so they describe the system as it is implemented.

| Diagram | Type | What it shows | Derived from |
|---|---|---|---|
| [System architecture](system-architecture.md) | flowchart | The Compose services, who talks to whom and over which interface | `compose.yaml`, `reverse-proxy/Caddyfile`, `monitoring/*.yml` |
| [Use cases](use-case.md) | flowchart (use case style) | What the Administrator, the Operator, Alertmanager and the Remediation Worker do | `backend/app/core/permissions.py`, `backend/app/api/*.py` |
| [System context](context.md) | flowchart | VigilOps, its users, the monitored demo application and the Google Gemini API | `compose.yaml`, `backend/app/assistant/gemini_provider.py` |
| [Data flow, level 1](data-flow.md) | flowchart (DFD) | Main processes, data stores and the data moving between them | `backend/app/services/*.py`, `backend/app/workers/*.py` |
| [Entity-relationship](er-diagram.md) | erDiagram | All thirteen tables with their main columns and relationships | `backend/app/models/models.py`, `backend/alembic/versions/0001_initial_schema.py` |
| [Incident lifecycle](incident-lifecycle.md) | stateDiagram-v2 | Incident statuses, allowed transitions and who may perform them | `backend/app/services/incident_service.py` |
| [Security scanning flow](security-scanning-flow.md) | flowchart | Target validation, rule evaluation and finding upsert, reopen and resolve | `backend/app/services/scan_service.py`, `backend/app/security_scanner/*.py` |
| [Remediation sequence](remediation-sequence.md) | sequenceDiagram | Request, approval, dispatch, execution, verification, success and failure | `backend/app/services/remediation_service.py`, `backend/app/workers/*.py` |
| [VigilAI architecture](vigilai-architecture.md) | flowchart | The assistant pipeline with its safeguards and the documentation fallback | `backend/app/assistant/*.py` |
| [Deployment](deployment.md) | flowchart | Containers, network, volumes and published ports, local and production | `compose.yaml`, `compose.prod.yaml` |

Two further state machines (security findings and remediation requests) are drawn inline in [../architecture.md](../architecture.md#state-machines).

## Conventions

- Node labels name the real service, function or table so that a diagram can be checked against the code.
- Dotted arrows mark relationships that exist only in demo mode or that are indirect (for example "queues work for").
- Text in the diagrams avoids HTML and uses quoted labels, which keeps them valid for GitHub's Mermaid renderer.

## Related documents

- [Architecture](../architecture.md)
- [API reference](../api.md)
- [Security](../security.md)
