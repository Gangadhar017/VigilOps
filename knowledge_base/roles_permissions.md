# Roles and Permissions

## Roles
VigilOps has two roles: Administrator and Operator. Permissions are enforced by the backend on every request; hiding a button in the interface is never the only control. A refused action returns HTTP 403 and is recorded in the audit trail as ACCESS_DENIED.

## Administrator permissions
An Administrator can do everything an Operator can, and additionally: approve and reject remediation requests, dispatch and retry remediation, close and reopen incidents, mark a finding as accepted risk, view the complete audit trail including sign-ins, manage users, change runtime settings and use the demo controls.

## Operator permissions
An Operator can view the dashboard, monitoring, incidents, findings, remediation and operational audit events; acknowledge incidents, mark them in progress, comment and resolve them with evidence; run security scans; request remediation and cancel their own pending requests; and use VigilAI. An Operator cannot approve or execute remediation, close incidents, manage users or change settings.

## Authentication
Users sign in with e-mail and password. Passwords are stored as bcrypt hashes. A successful login returns a signed JWT access token that expires after 60 minutes by default. Signing out revokes the token on the server. Changing a password or role signs out all of that user's sessions.

## Login rate limiting
After 5 failed sign-in attempts for the same e-mail and address within 5 minutes, further attempts are refused with HTTP 429 until the window passes. After 20 failed attempts for the same e-mail from any address within 5 minutes, sign-in for that e-mail is refused from every address until the window passes. Failed and blocked attempts are audited.

## Password policy
At least 10 characters, with upper-case and lower-case letters and a digit, and at most 72 bytes.

## Managing users
Administrators manage users in Settings -> Users: create a user, change role, deactivate or reactivate, and reset a password. There is no public self-registration. The last active Administrator cannot be demoted or deactivated.
