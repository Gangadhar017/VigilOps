# Alerting and Alert Management

## Alert rules
Alert rules are defined in monitoring/alert_rules.yml:
- ApplicationUnavailable (critical): up{job="demo-app"} == 0 for 15 seconds.
- HighHttp5xxErrorRate (high): more than 20% of responses are 5xx for 30 seconds.
- HighApiLatency (medium): p95 response time above 1 second for 30 seconds.
- HighCpuUsage (high): the process uses more than 80% of one CPU core for 30 seconds.
- HighMemoryUsage (high): resident memory above 250 MB for 30 seconds.

## Alertmanager
Alertmanager groups alerts by alert name and instance, waits 5 seconds before the first notification, and repeats notifications for alerts that are still firing every 2 minutes. It sends both firing and resolved notifications to the backend webhook.

## Protected webhook
Alertmanager calls POST /api/alerts/webhook with a bearer token (ALERT_WEBHOOK_TOKEN). Calls without the correct token are rejected with HTTP 401 and malformed payloads with HTTP 422. User login tokens are not accepted on this endpoint.

## Duplicate and repeated alerts
Each alert has a fingerprint derived from its labels. While an incident for that fingerprint is active (OPEN, ACKNOWLEDGED or IN_PROGRESS), repeated notifications only increase the incident's notification counter and update "last occurrence". A database unique index guarantees there is never more than one active incident per fingerprint.

## Resolved alerts
When Alertmanager reports an alert as resolved, the incident is resolved automatically and the monitoring signal is stored as verification evidence. If the same alert fires again within the reopen window (default 10 minutes, configurable in Settings) the existing incident is reopened instead of creating a new one. Closed incidents are never reopened automatically.

## Alert-to-incident delay
An incident appears after the scrape interval (5 seconds), the alert rule's "for" duration (15 seconds for ApplicationUnavailable, 30 seconds for the other rules), the rule evaluation interval and the Alertmanager group wait (5 seconds). For an outage that is about half a minute; the values measured on this installation are recorded in docs/evaluation.md.
