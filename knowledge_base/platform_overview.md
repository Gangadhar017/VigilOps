# VigilOps Platform Overview

## What VigilOps is
VigilOps: Secure Cloud Operations is a centralized cloud operations and security management platform. One web application brings together monitoring, incident management, security configuration scanning, controlled remediation, verification, audit history and the VigilAI assistant. All modules share one backend, one PostgreSQL database, one login and one navigation menu.

## Main modules and pages
- Overview: active incidents, findings by severity, remediation counts, latest scan, recent audit events and platform health.
- Monitoring: live Prometheus telemetry for monitored resources (availability, request rate, 4xx/5xx error rate, p95 latency, CPU, memory, uptime) and scrape target status.
- Incidents: incidents created automatically from Prometheus alerts, with a timeline, status workflow and linked remediation.
- Security Findings: results of the YAML configuration scanner for rules SEC-001 to SEC-005, scan history and finding lifecycle.
- Remediation: approval workflow for the supported automated actions ACTION-001 and ACTION-002, with execution and verification results.
- Audit Logs: searchable, append-only history of important events.
- VigilAI / Help: guidance on the assistant; the assistant itself is the floating chat icon at the bottom-right.
- Settings: profile, user management, runtime settings, permission matrix and demo controls.

## What VigilOps does not do
VigilOps does not connect to an AWS account and does not perform a live cloud security assessment. The scanner evaluates authorised local YAML configuration files. Automated remediation is limited to two explicitly supported actions. VigilOps never runs arbitrary shell commands and has no access to the Docker daemon or the host.

## Live data versus demonstration data
Monitoring values are real Prometheus samples; when a value cannot be obtained the page shows "unavailable" instead of a number. The demo application (OrbitCrate, a demonstration storefront at /orbitcrate/ whose orders are not real) receives synthetic traffic from a built-in load generator so that request metrics exist; requests made by visitors of the store are measured in the same way. Incidents caused by a controlled demo fault are labelled "Simulated fault". No incidents, findings or metrics are seeded: every record comes from real platform activity.
