# Incident Management

## Incident lifecycle
An incident moves through these statuses: OPEN -> ACKNOWLEDGED -> IN_PROGRESS -> RESOLVED -> CLOSED. Allowed transitions: OPEN to ACKNOWLEDGED, IN_PROGRESS or RESOLVED; ACKNOWLEDGED to IN_PROGRESS or RESOLVED; IN_PROGRESS to RESOLVED; RESOLVED to CLOSED or back to OPEN (reopen). CLOSED is final. Invalid transitions are rejected with HTTP 409.

## How incidents are created
Incidents are created by the incident engine when Alertmanager delivers a firing alert. The incident stores the alert name, severity, affected resource, alert fingerprint, detection time, latest occurrence and a notification counter.

## What an incident contains
ID, title, description, severity (CRITICAL, HIGH, MEDIUM, LOW), source, affected resource, alert fingerprint, status, detection timestamp, latest occurrence, resolution timestamp, an event timeline and any linked remediation requests. The detail page also shows possible causes, recommended steps and whether an automated action is supported.

## Resolving an incident
An incident is never resolved just because remediation was requested. It becomes RESOLVED only with evidence: 1) Alertmanager reports the alert as resolved; or 2) a remediation request succeeds after verification; or 3) a person resolves it manually with a written resolution note, which is only accepted when Prometheus no longer reports the alert as firing. If Prometheus cannot be reached at all, the request is refused as well, because recovery cannot be verified; only in that situation can an Administrator override the monitoring check with a documented reason, and the override is recorded in the audit trail. While Prometheus reports the alert as firing, nobody can resolve the incident manually.

## Who can change incident status
Operators and Administrators can acknowledge an incident, mark it in progress, add comments and resolve it with evidence. Only an Administrator can close or reopen an incident.

## Why an incident shows "Simulated fault"
The incident was opened while a controlled fault was active on the demonstration application (injected from Settings -> Demo controls). The telemetry and alert are real; only the cause is deliberate.

## Why an incident shows "Signal stale"
The alert is recorded as still firing, but Alertmanager has not repeated its notification for several minutes. The monitoring pipeline may be unhealthy; check Prometheus and Alertmanager on the Monitoring page.

## Investigating what caused an incident
Open the incident: the description and labels identify the alert rule and resource; the timeline shows when it fired and repeated; "Possible causes" and "Recommended steps" give the runbook. Then open Monitoring to see the related metrics for the same period.
