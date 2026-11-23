# Audit Logs

## What is recorded
Sign-ins, failed sign-ins and sign-outs; incident creation, status changes and resolution; security scans; finding detection, reopening and resolution; remediation requests, approvals, rejections, execution and verification results; user administration and settings changes; access-denied attempts; blocked VigilAI requests; and demo control usage.

## Audit record fields
Event ID, actor (user e-mail or a service identity such as alertmanager or the worker), action, entity type and ID, timestamp in UTC, outcome (SUCCESS, FAILURE or DENIED), safe metadata and a correlation ID. All events of one remediation workflow share the same correlation ID.

## Using the audit page
The Audit Logs page supports free-text search, filters by category, outcome and date range, sorting and pagination. Selecting an event shows its metadata.

## Who can see audit events
Administrators see every event. Operators see operational events (incidents, alerts, scans, findings, remediation, demo controls) and their own activity (such as their sign-ins).

## Audit integrity
Audit history is append-only. There is no API to edit or delete audit events, and in PostgreSQL a database trigger rejects UPDATE and DELETE on the audit table. Credentials, tokens and API keys are removed from audit metadata before it is stored.
