# Use Case Diagram

The use cases follow the permission matrix in `backend/app/core/permissions.py`: an Administrator can do everything an Operator can, plus the approval, closing, administration and demo-control use cases. Alertmanager and the Remediation Worker are system actors: the first feeds the incident engine through the protected webhook, the second executes and verifies only what an Administrator approved and dispatched.

```mermaid
flowchart LR
    operator["Operator"]
    admin["Administrator"]
    alertmgr["Alertmanager"]
    worker["Remediation Worker"]

    subgraph vigilops["VigilOps"]
        uc_auth(["Sign in, sign out, change own password"])
        uc_view(["View dashboard, monitoring and scrape targets"])
        uc_inc(["Acknowledge, work on, comment on and resolve incidents"])
        uc_scan(["Run security scans and review findings"])
        uc_req(["Request remediation and cancel own request"])
        uc_audit(["View operational audit events"])
        uc_ai(["Ask VigilAI, read-only answers"])
        uc_close(["Close or reopen incidents"])
        uc_risk(["Accept or revoke risk on a finding"])
        uc_approve(["Approve or reject remediation"])
        uc_exec(["Dispatch or retry remediation"])
        uc_users(["Manage users and runtime settings"])
        uc_fullaudit(["View the complete audit trail"])
        uc_demo(["Use demo controls, off in production by default"])
        uc_alert(["Deliver firing and resolved alerts"])
        uc_incident(["Create, deduplicate, reopen or resolve an incident"])
        uc_run(["Execute an allowlisted action"])
        uc_verify(["Verify the result with fresh evidence"])
    end

    admin -.->|"can do everything an Operator can"| operator

    operator --> uc_auth
    operator --> uc_view
    operator --> uc_inc
    operator --> uc_scan
    operator --> uc_req
    operator --> uc_audit
    operator --> uc_ai

    admin --> uc_close
    admin --> uc_risk
    admin --> uc_approve
    admin --> uc_exec
    admin --> uc_users
    admin --> uc_fullaudit
    admin --> uc_demo

    alertmgr --> uc_alert
    uc_alert -.->|"triggers"| uc_incident

    worker --> uc_run
    worker --> uc_verify
    uc_exec -.->|"queues work for"| uc_run
    uc_run -.->|"is followed by"| uc_verify
    uc_verify -.->|"may resolve"| uc_incident
```
