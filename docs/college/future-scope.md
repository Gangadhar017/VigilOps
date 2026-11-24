# VigilOps: Secure Cloud Operations - Future Scope

Realistic enhancements, grouped by theme. Each item states what it would add and why it is out of scope in the present build. The present limitations they respond to are listed in [`../architecture.md`](../architecture.md#known-limitations) and [`../security.md`](../security.md#residual-risks-and-limitations).

> **To be filled in by the team:** institution, guide, and the names and roll numbers of Member 1 to Member 4.

## Principles that any extension must keep

The enhancements below are worth doing only if they preserve the properties the project was built for:

1. **Nothing shown is invented.** A value is displayed only if it was measured or read from a real source; otherwise it is shown as unavailable.
2. **No arbitrary execution.** Corrective actions stay on an allowlist with one reviewed handler per action; a request never carries a command, script or path.
3. **Approval and separation of duties.** A change is requested by one person and approved by another; the component that decides is not the component that executes.
4. **Evidence-based success.** An action counts as successful only after independent verification.
5. **Append-only audit.** Every step leaves a record that the application cannot alter.
6. **The assistant stays read-only.** VigilAI may explain and report; it never changes platform or cloud state.

---

## 1. Optional read-only AWS integration

The project is local-first and needs no cloud account. A natural extension is to read real cloud state in addition to the local sample files, strictly read-only.

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| EC2 monitoring | Listing instances with their state and status checks as monitored resources next to the demonstration application | Requires an AWS account and credentials; the project was specified to run without any cloud account or cost |
| S3 configuration inspection | Reading the public-access and encryption settings of real buckets and evaluating them with the logic of SEC-001 and SEC-002 | The scanner's input is the local `vigilops/v1` YAML schema; a collector that maps provider responses to that schema does not exist yet |
| IAM policy assessment | Reading IAM policy documents and evaluating them with the logic of SEC-003; reading security-group rules for SEC-004 | Real policy documents are richer than the simplified statements the current rules understand (conditions, principals, managed policies); the rules would need to be extended and re-tested |
| CloudWatch metrics | A second telemetry source for resources that Prometheus cannot scrape | All telemetry currently comes from Prometheus; a second source needs its own availability handling so that the "never substitute a value" rule still holds |
| Credential handling for the collector | A dedicated identity with read-only permissions, short-lived credentials, and a clear display of which account and region are being read | No secret store exists beyond environment variables; cloud credentials deserve stronger handling than the present `.env` file |

**Boundary that must be stated in the report.** This integration is proposed as read-only. Any real mutation of an AWS account - for example changing a bucket's access settings, editing a policy or stopping an instance - is not a small extension of ACTION-002. It would need a separately reviewed security architecture (credential scope, blast radius, rollback, change windows, verification against the provider) and explicit authorization from the account owner before any implementation. Until then, remediation remains limited to the local demonstration environment.

---

## 2. Security scanning

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| More rules | Additional checks, for example logging disabled, backups not configured, containers running as root, unrestricted egress | Five rules were specified; each new rule needs catalog metadata, insecure and secure fixtures and tests to keep the "no false positives on secure fixtures" property |
| Real infrastructure-as-code formats | Scanning Terraform, Kubernetes manifests or CloudFormation instead of only the project's own schema | Each format needs its own parser and resource mapping; the project concentrated on the lifecycle around a finding rather than on format coverage |
| An established scanner as detection engine | Using a tool such as Checkov for detection and keeping VigilOps for lifecycle, approval, verification and audit | Would add an external dependency and a result-mapping layer; the small deterministic engine was easier to verify completely |
| Controlled upload of configuration files | An API to submit a file for scanning, with validation and review | Files reach the workspace only through the demo baseline or the host operator; an upload path is a new attack surface that needs its own design |
| A status for findings of removed files | A distinct state for findings whose configuration file no longer exists | A scan reports such findings in its summary but leaves their status unchanged, because a deleted file is not a verified fix; a new finding state would have to be designed and added to the lifecycle |

## 3. Remediation

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| More automated actions | Corrections for SEC-002 to SEC-005 in the sample configuration | Two actions were specified; each further action needs a handler, an independent verifier, an idempotency guarantee and failure tests |
| Preview before approval | Showing the Administrator the exact diff an action would produce before it is approved | The diff is produced during execution; a dry-run mode per handler has not been written |
| Rollback action | An allowlisted action that restores the configuration recorded before a change | The before and after state is stored with each execution, but no handler uses it yet |
| Comment-preserving edits | Keeping comments and formatting when ACTION-002 changes a file | The handler re-serialises the YAML document and preserves only the leading comment block; a round-trip YAML library would have to be introduced and tested |
| Starting a stopped container | Recovering from a stopped demonstration container | Needs access to the Docker daemon, which the platform deliberately does not have; it would require a separately designed, narrowly scoped mechanism |
| Several workers and hard action timeouts | More than one worker claiming jobs in parallel, and handlers that can be stopped when they exceed their timeout | The queue is already safe for several workers (`SKIP LOCKED`), but the deployment defines one worker that processes one job at a time; an action that exceeds its timeout is abandoned, not killed, because it runs in a thread |
| Stricter approval for risky actions | Two approvers or an approval expiry for higher-risk actions | With two low-risk demonstration actions a single approval by a second person was sufficient |

## 4. Monitoring

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Node and container exporters | Host metrics (CPU, memory, disk, network) and per-container resource metrics | The current metrics come from each process's own instrumentation; exporters need host mounts and privileges that were avoided in the hardened local stack |
| Probing from outside | Black-box checks of endpoints as a user would reach them | Availability is derived from scrape success; an external probe service was not needed for one application |
| Registering monitored resources through the interface | Adding a resource and its alert rules without editing files | Resources are registered at start-up and the alert rules target the job `demo-app`; dynamic registration needs generated scrape and rule configuration and a reload mechanism |
| Dashboards in Grafana | Richer, user-defined visualisation | The built-in pages cover the catalog metrics; adding Grafana means another service and another login |
| Log aggregation | Searching application logs next to metrics | Logs are structured JSON on standard output but are not collected centrally |

## 5. Incident management

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Notification channels | E-mail, chat or on-call notifications when an incident opens or a request awaits approval | Alertmanager is configured with one receiver, the platform's own webhook; external channels need credentials for third-party services and were excluded by the "no paid service" requirement |
| Assignment and escalation | An owner per incident, reminders and escalation after a time limit | The lifecycle records who acted but has no assignment field or timers |
| Grouping related alerts | One incident for several alerts with a common cause | Deduplication is by alert fingerprint only; correlation across alerts needs rules about resources and time |
| Silences and maintenance windows from the interface | Suppressing alerts during planned work | Would require writing to Alertmanager, which the backend currently only reads |
| Post-incident review | A structured review record linked to the incident | The timeline and resolution evidence exist; a review template was not specified |

## 6. Identity and access

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Multi-factor authentication | A second factor such as a time-based one-time code | A password is the only factor; the specification asked for two roles with password sign-in |
| Single sign-on | Sign-in through an institutional identity provider (OpenID Connect or SAML) | Needs an external identity provider, which conflicts with the self-contained local-first setup |
| More roles and ownership | For example a read-only auditor, or ownership of resources by teams | Two fixed roles were specified; there is no per-object ownership beyond "own remediation request" |
| Self-service password reset and stronger password checks | Reset by e-mail; rejection of known-breached passwords | No e-mail service is configured; an Administrator resets passwords |
| Refresh tokens and asymmetric signing | Longer sessions without long-lived access tokens; key rotation without signing everyone out | A single 60-minute HS256 token with server-side revocation was sufficient for the demonstration |

## 7. Security hardening

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Separate database roles | The API unable to modify audit rows or forge queue entries; the worker limited to its queue | Both processes use the role created by the PostgreSQL image; table-level grants need a migration and role provisioning step |
| Tamper-evident audit trail | A hash chain over audit events or export to an external log store | The trail is append-only against the application, not tamper-evident against a database administrator |
| Trusting forwarded headers only from the proxy | A client address that cannot be spoofed by another container | The setting is configurable but defaults to trusting any peer on the private network |
| Encryption inside the Docker network | TLS between proxy, backend and database | Internal traffic is plain on a private bridge network on one host |
| Secret store | Secrets delivered by a dedicated manager instead of a `.env` file | Environment variables were adequate for a single-host demonstration |

## 8. Scalability and reliability

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Redis-backed rate limiting | Limits shared across processes and surviving restarts | The limiter is in process memory by design, to avoid another service; it requires a single backend process |
| Multi-instance backend | Several stateless API replicas behind the proxy | The rate limiters, the monitoring cache and the assistant's daily budget are in memory; they must move to a shared store first |
| Highly available database | Replication and automatic failover, or a managed database service | One PostgreSQL container with a volume and backup scripts was sufficient for a single-host project |
| Push updates | Server-sent events or WebSockets instead of polling | Polling every few seconds is simple and adequate for two users |
| Message broker for the queue | Higher throughput and delayed jobs | The database queue keeps the request, its state and its audit trail in one transaction and is ample for the present volume |

## 9. VigilAI

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Wider evaluation of live Gemini mode | A systematic human evaluation of answer quality on a larger fixed question set, a comparison of models, and an observation of real quota exhaustion (HTTP 429 from the provider) | The baseline is done: live generation was verified with a real API key and one model on a small question set, using keyword grounding checks and a reading of the replies (`scripts/verify_gemini_live.py`, `docs/evidence/gemini-live.json`). Quota exhaustion and provider timeouts are covered only by tests with a stubbed SDK client |
| Vector or hybrid retrieval | Semantic matching when the wording of a question differs from the documentation | The knowledge base is a small set of Markdown files dominated by exact terms; BM25 is deterministic, explainable and needs no extra service. This becomes worthwhile if the knowledge base grows substantially |
| Model-selected read-only functions | Letting the model choose among the existing read-only functions with strict schemas | Keyword routing was chosen so that a manipulated model cannot widen what is read; changing this needs a new threat analysis even though the functions stay read-only |
| Answer feedback and evaluation set | Collecting "helpful / not helpful" and re-testing after knowledge-base changes | Usage is logged as metadata only; question and answer text is deliberately not stored |
| Other providers | A second model vendor or a locally hosted model | The provider interface allows it, but only the Gemini provider is implemented, and local model hosting was excluded by the specification |

## 10. Deployment and operations

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Verified public HTTPS deployment | Evidence that the production overlay obtains a certificate and serves the application on a real domain | The overlay was validated as configuration only; no server and domain were available |
| Kubernetes deployment | Manifests or a Helm chart, using the existing liveness and readiness endpoints as probes | Docker Compose on one host met the specification; Kubernetes adds a cluster to operate |
| Scheduled backups | Automatic, rotated database backups with a tested restore | Backup and restore are manual scripts |
| Supply-chain checks in CI | Dependency audit and container image scanning | The CI workflow runs linting, tests, configuration validation and the end-to-end demonstrations |

## 11. Testing

| Enhancement | What it would add | Why it is out of scope today |
|---|---|---|
| Wider browser coverage | The Playwright tests also run in Firefox and WebKit, and the application failure and recovery demonstration is driven through the pages | Nine Playwright tests in `tests/e2e/` run in Chromium and cover sign-in, navigation, monitoring, role restrictions, the assistant widget and the security remediation workflow; Demo 1 is automated at the API level only |
| Load and soak tests | Behaviour under many users and over long periods | The system was built and evaluated for a demonstration with two users on one machine |
| Fault-injection tests of the platform itself | Behaviour when PostgreSQL, Prometheus or the worker fail in the middle of a workflow | Individual failure paths are covered by integration tests with fakes; systematic injection against the running stack was not done |

---

## Suggested order

1. Verify what is currently unverified: the public HTTPS deployment and the assistant's behaviour when the Gemini quota is really exhausted. These need no new code, only a server with a domain, an API key and a recorded run.
2. Close the security gaps that need little code: separate database roles for the API and the worker, and trusting forwarded headers only from the proxy.
3. Add value inside the existing design: more rules with fixtures, a preview of the diff before approval, a rollback action, notification through a webhook.
4. Remove the single-instance constraint: shared rate-limit store, then several backend replicas.
5. Only then widen the scope: read-only AWS collection, real infrastructure-as-code formats, Kubernetes.

Each step should be accompanied by tests and by an update of the knowledge base and the documents in `docs/`, and each new measured value should be added to [`../evaluation.md`](../evaluation.md) with the date and conditions of the run.
