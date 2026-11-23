# Security Rules and Scanner

## Scanner scope
The security scanner is a deterministic Python engine. It evaluates authorised local YAML configuration files in the scan workspace that follow the vigilops/v1 schema (a list of resources with a type and a name). It is not a live AWS or cloud account assessment. Five rules are implemented: SEC-001 to SEC-005.

## SEC-001 Public Storage Access
SEC-001 means a storage bucket allows anonymous public access. Severity HIGH. It is detected when public_access is true, or when acl is public-read or public-read-write. Impact: anyone on the internet can list or download the objects, and with public write can tamper with them. Fix: set public_access: false and acl: private, and grant access to specific identities instead. SEC-001 is the only rule with automated remediation (ACTION-002).

## SEC-002 Missing Encryption
SEC-002 means data at rest is not encrypted. Severity MEDIUM. It is detected for a storage_bucket, disk_volume or database whose encryption block is missing, whose encryption.enabled is not true, or whose algorithm is empty or NONE. Impact: data, snapshots and backups can be read in clear text if the storage is exposed. Fix: set encryption.enabled: true with a strong algorithm such as AES-256. There is no automated action; apply the change manually and rescan.

## SEC-003 Wildcard IAM Permissions
SEC-003 means an IAM policy is overly broad. Severity CRITICAL. It is detected for a statement with effect Allow whose actions contain "*" or a service-wide wildcard such as "s3:*", or whose resources contain "*". Impact: a compromised identity can perform any action, which defeats least privilege. Fix: list only the specific actions and resource identifiers the workload needs. No automated action.

## SEC-004 Unrestricted Inbound Network Access
SEC-004 means a sensitive port is open to the whole internet. Severity HIGH. It is detected for a security group ingress rule open to 0.0.0.0/0 or ::/0 that includes a sensitive port: 22 SSH, 23 Telnet, 3389 RDP, 1433 MSSQL, 3306 MySQL, 5432 PostgreSQL, 6379 Redis, 9200 Elasticsearch or 27017 MongoDB. Port ranges are checked too. Ports 80 and 443 open to the internet are not flagged. Fix: restrict the source CIDR to trusted ranges or use a bastion host or VPN. No automated action.

## SEC-005 Privileged Container Execution
SEC-005 means a container runs in privileged mode. Severity HIGH. It is detected for a container with privileged: true or security_context.privileged: true. Impact: a privileged container has nearly full host kernel capabilities, so a container escape becomes a host compromise. Fix: set privileged: false and add only the specific Linux capabilities required. No automated action.

## Running a scan
Open Security Findings and choose "Run scan". Without a target, every YAML file in the scan workspace is scanned. Operators and Administrators can run scans. Each scan is stored in the scan history with its counts.

## Finding lifecycle
OPEN: detected and not yet addressed. REMEDIATION_PENDING: a remediation request is in progress. RESOLVED: a later scan no longer detects the violation. ACCEPTED_RISK: an Administrator recorded a justification for not fixing it. Findings are never deleted or hidden: a finding becomes RESOLVED only when a scan verifies the rule is no longer violated, and it is reopened automatically if the violation returns.

## Duplicate findings
Each finding has a stable key computed from the file, rule, resource type and resource name. Repeated scans update the same finding (last seen time and detection count) instead of creating duplicates.

## Scanner safety
The scanner uses safe YAML parsing, rejects anchors and aliases, limits file size, accepts only plain .yaml or .yml file names inside the authorised workspace and blocks directory traversal. Wrongly typed fields (for example public_access written as the text "true" instead of the boolean true) make the file malformed. Malformed files are rejected and reported, and their existing findings are left unchanged.
