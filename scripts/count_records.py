#!/usr/bin/env python3
"""Print how many records of each kind the running platform holds (as JSON).

    python scripts/count_records.py

Used to confirm that data survives container restarts and backup/restore:
run it before and after, and compare.  Standard library only; signs in with
the bootstrap Administrator from .env.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_e2e_demos import ROOT, Api, load_env  # noqa: E402


def main() -> int:
    env = load_env(ROOT / ".env")
    api = Api(f"http://localhost:{env.get('VIGILOPS_HTTP_PORT', '8080')}")
    token = api.login(env["BOOTSTRAP_ADMIN_EMAIL"], env["BOOTSTRAP_ADMIN_PASSWORD"])
    counts = {}
    for name, path in (
        ("users", "/api/users?page_size=1"),
        ("incidents", "/api/incidents?page_size=1"),
        ("security_scans", "/api/security/scans?page_size=1"),
        ("security_findings", "/api/security/findings?page_size=1"),
        ("remediation_requests", "/api/remediation/requests?page_size=1"),
        ("audit_events_before_this_login", "/api/audit/events?page_size=1"),
    ):
        status, body = api.call("GET", path, token)
        counts[name] = body["total"] if status == 200 else f"HTTP {status}"
    # This script's own sign-in adds one audit event; report the count without it.
    if isinstance(counts["audit_events_before_this_login"], int):
        counts["audit_events_before_this_login"] -= 1
    status, body = api.call("GET", "/api/remediation/requests?status=SUCCEEDED&page_size=1", token)
    counts["remediation_succeeded"] = body["total"] if status == 200 else f"HTTP {status}"
    status, body = api.call("GET", "/api/security/findings?status=RESOLVED&page_size=1", token)
    counts["findings_resolved"] = body["total"] if status == 200 else f"HTTP {status}"
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
