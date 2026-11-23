# Entity-Relationship Diagram

The diagram lists the thirteen tables defined in `backend/app/models/models.py` (created by the Alembic migration `0001_initial_schema.py`) with their main columns. `worker_heartbeats` has no foreign keys; all timestamps are timezone-aware UTC, and the JSON column shown as `metadata` is mapped to the Python attribute `event_metadata`.

```mermaid
erDiagram
    users ||--o{ revoked_tokens : "has revoked"
    users ||--o{ remediation_requests : "requested_by"
    users |o--o{ remediation_requests : "approved_by"
    users |o--o{ audit_events : "actor_id"
    users |o--o{ incident_events : "actor_id"
    users |o--o{ security_scans : "requested_by"
    users |o--o{ security_findings : "accepted_risk_by"
    users |o--o{ system_settings : "updated_by"
    users |o--o{ demo_tasks : "requested_by"
    monitored_resources |o--o{ incidents : "resource_id"
    incidents ||--o{ incident_events : "timeline"
    incidents |o--o{ remediation_requests : "incident_id"
    security_scans |o--o{ security_findings : "scan_id first detected"
    security_scans |o--o{ security_findings : "last_scan_id last evaluated"
    security_findings |o--o{ remediation_requests : "finding_id"
    remediation_requests ||--o{ remediation_executions : "attempts"

    users {
        int id PK
        string email UK
        string full_name
        string password_hash "bcrypt"
        string role "admin or operator"
        bool is_active
        int token_version "bumped to invalidate all tokens"
        datetime last_login_at
        datetime created_at
        datetime updated_at
    }

    revoked_tokens {
        string jti PK "JWT id revoked by logout"
        int user_id FK
        datetime expires_at
        datetime revoked_at
    }

    monitored_resources {
        int id PK
        string name UK
        string resource_type
        string environment
        string monitoring_identifier UK "Prometheus job label"
        string description
        string status "UP, DOWN or UNKNOWN"
        datetime status_checked_at
        datetime created_at
        datetime updated_at
    }

    incidents {
        int id PK
        string title
        text description
        string severity "CRITICAL, HIGH, MEDIUM, LOW"
        string status "OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED, CLOSED"
        string source
        string alert_name
        string alert_fingerprint "unique among active incidents"
        int resource_id FK
        string affected_resource
        json labels
        json annotations
        string action_code "suggested allowlisted action"
        bool is_simulated
        string simulation_note
        bool alert_active
        int occurrence_count
        datetime detected_at
        datetime last_occurrence_at
        datetime acknowledged_at
        datetime resolved_at
        datetime closed_at
        text resolution_summary
        datetime created_at
        datetime updated_at
    }

    incident_events {
        int id PK
        int incident_id FK
        int actor_id FK
        string actor_label
        string event_type
        string previous_state
        string new_state
        text details
        json metadata
        datetime created_at
        datetime updated_at
    }

    security_scans {
        int id PK
        int requested_by FK
        string requested_by_label
        string trigger "MANUAL, REMEDIATION_VERIFICATION, DEMO_RESET"
        string target "file name or * for all"
        string status "RUNNING, COMPLETED, FAILED"
        datetime started_at
        datetime completed_at
        json result_summary
        text error
    }

    security_findings {
        int id PK
        int scan_id FK
        int last_scan_id FK
        string stable_finding_key UK "sha256 of file, rule, resource type, resource name"
        string rule_id
        string rule_name
        string severity
        string target_file
        string resource_type
        string resource_name
        string resource_identifier
        json evidence
        text recommendation
        string status "OPEN, REMEDIATION_PENDING, RESOLVED, ACCEPTED_RISK"
        int detection_count
        datetime first_detected_at
        datetime last_seen_at
        datetime resolved_at
        int accepted_risk_by FK
        text accepted_risk_reason
        datetime accepted_risk_at
        datetime created_at
        datetime updated_at
    }

    remediation_requests {
        int id PK
        string correlation_id "links all audit events of one workflow"
        string source_type "incident or finding"
        int incident_id FK
        int finding_id FK
        string action_code "ACTION-001 or ACTION-002"
        string target
        int requested_by FK
        int approved_by FK
        string status "nine workflow states"
        text justification
        text decision_comment
        int attempt_count
        int max_attempts
        text failure_reason
        datetime created_at
        datetime updated_at
        datetime decided_at
        datetime queued_at
        datetime started_at
        datetime completed_at
    }

    remediation_executions {
        int id PK
        int request_id FK
        int attempt "unique per request"
        string worker_identifier
        string status "RUNNING, VERIFYING, SUCCEEDED, FAILED"
        json execution_details
        json verification_result
        text error
        datetime started_at
        datetime completed_at
    }

    audit_events {
        int id PK
        string event_id UK "UUID"
        int actor_id FK
        string actor_label
        string action
        string entity_type
        string entity_id
        string outcome "SUCCESS, FAILURE, DENIED"
        json metadata
        string correlation_id
        string source_ip
        datetime created_at
    }

    system_settings {
        string key PK
        json value
        int updated_by FK
        datetime updated_at
    }

    worker_heartbeats {
        string worker_id PK
        string hostname
        string version
        datetime started_at
        datetime last_seen_at
        int jobs_processed
    }

    demo_tasks {
        int id PK
        string task_type
        string status "QUEUED, RUNNING, SUCCEEDED, FAILED"
        int requested_by FK
        json details
        text error
        datetime created_at
        datetime started_at
        datetime completed_at
    }
```

Constraints that the diagram cannot express (partial unique indexes, CHECK constraints, the append-only trigger on `audit_events`) are described in [../architecture.md](../architecture.md#database-design).
