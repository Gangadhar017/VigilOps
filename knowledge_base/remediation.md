# Remediation Workflow

## Remediation approval process
1) An Operator (or Administrator) opens an incident or finding and requests remediation with a justification. The request starts in PENDING_APPROVAL. 2) An Administrator reviews it on the Remediation page and approves (APPROVED) or rejects (REJECTED) it. 3) The Administrator dispatches the approved request ("Execute"), which queues it (QUEUED). 4) The restricted worker runs the action (RUNNING) and then verifies the result (VERIFYING). 5) The request ends as SUCCEEDED only if verification passes, otherwise FAILED. Every step is written to the audit trail.

## Remediation statuses
PENDING_APPROVAL, APPROVED, REJECTED, QUEUED, RUNNING, VERIFYING, SUCCEEDED, FAILED and CANCELLED.

## Who can approve remediation
Only an Administrator can approve, reject, dispatch or retry. An Operator can request remediation, watch its progress and cancel their own request before it is dispatched. By default an Administrator cannot approve a request they submitted themselves; a second person must review it. This can be changed in Settings (remediation.allow_self_approval).

## ACTION-001 Recover the demonstration application
Applies to incidents on the demo application. The worker calls the application's token-protected internal recovery endpoint, which re-initialises its service component and clears the fault. Verification requires three consecutive successful readiness checks, a successful Prometheus scrape newer than the action, and the original alert no longer firing. The linked incident is then resolved with this evidence. ACTION-001 cannot start a stopped container: VigilOps has no Docker or host access by design.

## ACTION-002 Correct public storage configuration
Applies to SEC-001 findings in an allowlisted configuration file. The worker sets public_access: false and acl: private for the affected bucket, writes the file atomically and records a before/after diff. It then runs the security scanner again; the request succeeds only if SEC-001 is no longer detected for that resource. The finding is resolved by the scan itself, never set by hand.

## How to fix public storage access
Open the SEC-001 finding, choose "Request remediation" (ACTION-002) and give a justification. After an Administrator approves and dispatches it, the worker corrects the configuration and re-scans. To fix it manually instead, set public_access: false and acl: private in the YAML file and run a scan.

## When automated remediation is not available
For SEC-002, SEC-003, SEC-004 and SEC-005 and for incidents on other resources there is no automated action. VigilOps still shows the possible cause and recommended corrective steps; apply them manually and verify with a new scan or by watching the alert clear.

## Failed remediation and retries
If the action cannot be carried out or verification fails, the request becomes FAILED with the reason. The problem is treated as not fixed: the finding returns to OPEN and the incident stays open. An Administrator can retry a failed request up to the attempt limit (3). Transient errors inside an action are retried automatically with a short back-off, and each action has an execution timeout.

## Remediation safety rules
Only the allowlisted action codes can be requested; there is no field for a command, script or path. No arbitrary shell commands, no AI-generated commands, no host filesystem or Docker access, no production cloud changes, and no way to bypass approval: the worker refuses any queued request without a recorded approval. VigilAI cannot approve or execute remediation.

## Checking the status of a remediation request
Open the Remediation page and select the request. It shows the current status, who requested and approved it, each execution attempt, the verification checks and the audit timeline. You can also ask VigilAI "What is the status of my remediation request?".
