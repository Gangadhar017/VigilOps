# Security Scanning Flow

A scan evaluates authorised YAML files from the scan workspace against rules SEC-001 to SEC-005 and then reconciles the result with the stored findings: new violations create findings, known ones are updated, returning ones are reopened and violations that disappeared are resolved. A file that fails validation is reported in the scan summary and its existing findings are left untouched.

```mermaid
flowchart TD
    start(["POST /api/security/scans"]) --> perm{"Permission scans:run?"}
    perm -->|"no"| denied["HTTP 403 and ACCESS_DENIED audit event"]
    perm -->|"yes"| hasTarget{"Target name given?"}
    hasTarget -->|"yes"| resolveT{"resolve_target: plain .yaml or .yml name, resolved path directly inside the workspace, file exists"}
    hasTarget -->|"no"| listAll["list_targets: every valid file in the workspace"]
    resolveT -->|"invalid"| rejected["HTTP 400 or 404, no scan is recorded"]
    resolveT -->|"valid"| scanRow["Insert security_scans row, status RUNNING"]
    listAll --> scanRow
    scanRow --> perFile["For each file"]
    perFile --> load{"load_document: size limit, UTF-8, no anchors or aliases, yaml.safe_load, schema_version vigilops/v1, resource list checks"}
    load -->|"rejected"| fileErr["Record the file error in the summary, keep its findings unchanged"]
    load -->|"accepted"| evaluate["evaluate_document: every applicable rule on every resource, one violation per rule and resource"]
    evaluate --> key["Stable key: sha256 of file, rule id, resource type, resource name"]
    key --> known{"Finding with this key exists?"}
    known -->|"no"| create["Insert finding OPEN, audit FINDING_DETECTED"]
    known -->|"yes, RESOLVED"| reopen["Set OPEN again, audit FINDING_REOPENED"]
    known -->|"yes, other status"| update["Update last seen, evidence and detection count, keep status"]
    evaluate --> gone{"Stored finding of this file not detected now and not RESOLVED?"}
    gone -->|"yes"| resolveF["Set RESOLVED, audit FINDING_RESOLVED"]
    fileErr --> finish
    create --> finish
    reopen --> finish
    update --> finish
    resolveF --> finish
    finish["Scan COMPLETED, or FAILED when no file could be scanned. Store result_summary, audit SECURITY_SCAN_COMPLETED or SECURITY_SCAN_FAILED, commit"]
```

The same `run_scan` function is used by the worker to verify ACTION-002 (trigger `REMEDIATION_VERIFICATION`) and by the demo reset (trigger `DEMO_RESET`).
