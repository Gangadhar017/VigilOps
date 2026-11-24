#!/usr/bin/env python3
"""Demonstrate a remediation that FAILS, against a RUNNING Compose stack.

    docker compose up --build -d
    python scripts/run_failed_remediation_demo.py

The other demonstrations (scripts/run_e2e_demos.py) show remediation working.
This one shows what the platform does when it does not:

1. the monitored application's container is really stopped (not a simulated
   fault), so the recovery endpoint that ACTION-001 calls cannot be reached,
2. the alert fires and an incident opens - without the "simulated" label,
3. the Operator requests ACTION-001, the Administrator approves and dispatches,
4. the worker tries, cannot reach the application and reports FAILED,
5. the incident stays open, the failure is on its timeline and in the audit
   trail, and nothing claims success,
6. the container is started again (the cause is fixed outside the platform),
7. the Administrator retries the failed request; this time it is executed and
   verified, and the incident is resolved.

It needs the Docker CLI (to stop and start the container) and the bootstrap
accounts from .env.  Standard library only.  Every check is recorded as PASS or
FAIL with what was observed; results go to docs/evidence/failed-remediation.json.

Exit code: 0 if every check passed, 1 otherwise.  The container is started
again even if a check fails or the script is interrupted.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from run_e2e_demos import ROOT, Api, Recorder, load_env, wait_for

SERVICE = "test-app"
ACTION = "ACTION-001"
ALERT = "ApplicationUnavailable"
JUSTIFICATION = "Failed-run demonstration: recover the stopped application."


def compose(command: List[str], *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([*command, *arguments], cwd=str(ROOT), capture_output=True, text=True, timeout=120)


def demo_resource(api: Api, token: str) -> Optional[Dict[str, Any]]:
    status, overview = api.call("GET", "/api/monitoring/overview", token)
    if status != 200:
        return None
    return next((resource for resource in overview["resources"] if resource["job"] == "demo-app"), None)


def run(api: Api, admin: str, operator: str, rec: Recorder, docker: List[str]) -> None:
    rec.demo = "DEMO 4 - Remediation that fails, and its retry"
    print(f"\n=== {rec.demo} ===")

    api.call("POST", "/api/demo/faults", admin, {"mode": "none"})  # no simulated fault may be active
    healthy, _ = wait_for(lambda: (lambda r: r if r and r["status"] == "UP" else None)(demo_resource(api, operator)), timeout=60)
    rec.check("1. The application is healthy before the test", bool(healthy), (healthy or {}).get("status", "not UP"))

    # Close leftovers so that this run opens a fresh incident.
    _, old = api.call("GET", f"/api/incidents?status=RESOLVED&q={ALERT}&page_size=100", admin)
    for incident in (old or {}).get("items", []):
        api.call("POST", f"/api/incidents/{incident['id']}/transition", admin, {"status": "CLOSED", "note": "Closed before the failed-run demonstration."})

    stopped_at = time.time()
    stopped = compose(docker, "stop", SERVICE)
    rec.check("2. The application container is stopped (a real outage, not an injected fault)", stopped.returncode == 0, (stopped.stderr or stopped.stdout).strip().splitlines()[-1:] or "stopped")
    if stopped.returncode != 0:
        return

    down, waited = wait_for(lambda: (lambda r: r if r and r["status"] == "DOWN" else None)(demo_resource(api, operator)), timeout=60, interval=1.0)
    rec.check("3. Monitoring reports the scrape target DOWN", bool(down), f"after {waited:.1f}s")

    def incident_open():
        _, listing = api.call("GET", f"/api/incidents?active_only=true&q={ALERT}", operator)
        return listing["items"][0] if listing and listing.get("items") else None

    incident, _ = wait_for(incident_open, timeout=150, interval=1.0)
    rec.check("4. The alert opens an incident", bool(incident), (incident or {}).get("title", "no incident within 150 s"))
    if not incident:
        return
    iid = incident["id"]
    rec.measure("stop_to_incident_seconds", round(time.time() - stopped_at, 1), "s (container stop -> incident visible)")
    rec.check("4b. The incident is NOT labelled as simulated: nothing was injected", incident["is_simulated"] is False, f"is_simulated={incident['is_simulated']}")

    status, request = api.call("POST", "/api/remediation/requests", operator, {
        "source_type": "incident", "source_id": iid, "action_code": ACTION, "justification": JUSTIFICATION,
    })
    rec.check("5. Operator requests ACTION-001 -> PENDING_APPROVAL", status == 201 and request["status"] == "PENDING_APPROVAL", (request or {}).get("status", f"HTTP {status}"))
    if status != 201:
        return
    rid = request["id"]
    status, approved = api.call("POST", f"/api/remediation/requests/{rid}/approve", admin, {"comment": "Failed-run demonstration approval"})
    rec.check("6. Administrator approves", status == 200 and approved["status"] == "APPROVED", (approved or {}).get("status"))
    dispatched = time.monotonic()
    status, queued = api.call("POST", f"/api/remediation/requests/{rid}/execute", admin)
    rec.check("7. Administrator dispatches to the worker", status == 200 and queued["status"] == "QUEUED", (queued or {}).get("status"))

    def finished():
        _, current = api.call("GET", f"/api/remediation/requests/{rid}", admin)
        return current if current and current["status"] in ("SUCCEEDED", "FAILED") else None

    failed, waited = wait_for(finished, timeout=120, interval=1.0)
    rec.check("8. The worker reports the run as FAILED", bool(failed) and failed["status"] == "FAILED", (failed or {}).get("status", f"no result after {waited:.0f}s"))
    if not failed or failed["status"] != "FAILED":
        return
    rec.measure("dispatch_to_failed_seconds", round(time.monotonic() - dispatched, 1), "s (dispatch -> FAILED, three recovery calls with back-off)")
    rec.check("8b. The failure reason says what happened", "could not be reached" in (failed.get("failure_reason") or ""), failed.get("failure_reason"))
    execution = failed["executions"][-1]
    calls = (execution.get("execution_details") or {}).get("recovery_calls", [])
    rec.check(
        "8c. The execution record shows the three unanswered recovery calls",
        execution["status"] == "FAILED" and len(calls) == 3 and all("error" in call for call in calls),
        [call.get("error") or call.get("status_code") for call in calls],
    )
    rec.check("8d. One of three attempts was used; a retry is still possible", (failed["attempt_count"], failed["max_attempts"]) == (1, 3), f"{failed['attempt_count']} of {failed['max_attempts']}")

    _, current = api.call("GET", f"/api/incidents/{iid}", operator)
    rec.check("9. The incident is still active: a failed fix resolves nothing", current["status"] in ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS"), current["status"])
    timeline = [event["event_type"] for event in current.get("events", [])]
    rec.check("9b. The failure is on the incident's timeline", "REMEDIATION_FAILED" in timeline, [name for name in timeline if name.startswith("REMEDIATION")])
    status, body = api.call("POST", f"/api/incidents/{iid}/transition", operator, {"status": "RESOLVED", "note": "Trying to resolve while the application is down."})
    rec.check("9c. Resolving by hand is refused while the alert is firing", status == 409, (body or {}).get("detail"))

    _, audit = api.call("GET", f"/api/audit/events?correlation_id={failed['correlation_id']}&page_size=100&order=asc", admin)
    events = {event["action"]: event["outcome"] for event in audit["items"]}
    rec.check("10. The audit trail records the failure as a failure", events.get("REMEDIATION_FAILED") == "FAILURE" and "REMEDIATION_SUCCEEDED" not in events, events)

    # --- the cause is fixed outside the platform, then the request is retried ---
    started = compose(docker, "start", SERVICE)
    rec.check("11. The application container is started again", started.returncode == 0, (started.stderr or started.stdout).strip().splitlines()[-1:] or "started")
    up, waited = wait_for(lambda: (lambda r: r if r and r["status"] == "UP" else None)(demo_resource(api, operator)), timeout=90, interval=1.0)
    rec.check("11b. Monitoring reports the scrape target UP again", bool(up), f"after {waited:.1f}s")

    retried_at = time.monotonic()
    status, retried = api.call("POST", f"/api/remediation/requests/{rid}/retry", admin)
    rec.check("12. Administrator retries the failed request -> QUEUED", status == 200 and retried["status"] == "QUEUED", (retried or {}).get("status", f"HTTP {status}"))
    final, waited = wait_for(finished, timeout=240, interval=2.0)
    rec.check("13. The second attempt is executed and verified -> SUCCEEDED", bool(final) and final["status"] == "SUCCEEDED", (final or {}).get("failure_reason") or (final or {}).get("status", f"no result after {waited:.0f}s"))
    if not final:
        return
    rec.measure("retry_to_verified_seconds", round(time.monotonic() - retried_at, 1), "s (retry -> verified result, includes waiting for the alert to clear)")
    rec.check("13b. Both attempts are kept: the failed one and the successful one", [item["status"] for item in final["executions"]] == ["FAILED", "SUCCEEDED"] and final["attempt_count"] == 2, [item["status"] for item in final["executions"]])

    resolved, _ = wait_for(lambda: (lambda i: i if i and i["status"] == "RESOLVED" else None)(api.call("GET", f"/api/incidents/{iid}", operator)[1]), timeout=180, interval=2.0)
    rec.check("14. The incident is RESOLVED, with how it was resolved", bool(resolved), (resolved or {}).get("resolution_summary", "not resolved within 180 s"))

    _, audit = api.call("GET", f"/api/audit/events?correlation_id={final['correlation_id']}&page_size=100&order=asc", admin)
    actions = [event["action"] for event in audit["items"]]
    wanted = ["REMEDIATION_REQUESTED", "REMEDIATION_APPROVED", "REMEDIATION_FAILED", "REMEDIATION_RETRY_QUEUED", "REMEDIATION_SUCCEEDED"]
    positions = [actions.index(name) if name in actions else -1 for name in wanted]
    rec.check("15. Audit history shows request, approval, failure, retry and success in that order", -1 not in positions and positions == sorted(positions), [name for name in actions if name.startswith("REMEDIATION")])
    status, closed = api.call("POST", f"/api/incidents/{iid}/transition", admin, {"status": "CLOSED", "note": "Reviewed after the failed-run demonstration."})
    rec.check("16. Administrator closes the incident after review", status == 200 and closed["status"] == "CLOSED", (closed or {}).get("status", f"HTTP {status}"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=None, help="default: http://localhost:<VIGILOPS_HTTP_PORT>")
    parser.add_argument("--compose", default="docker compose", help='how to call Docker Compose (default: "docker compose")')
    parser.add_argument("--no-save", action="store_true", help="do not write docs/evidence/failed-remediation.json")
    args = parser.parse_args()
    docker = shlex.split(args.compose)

    env = load_env(ROOT / ".env")
    api = Api(args.base_url or f"http://localhost:{env.get('VIGILOPS_HTTP_PORT', '8080')}")
    status, health = api.call("GET", "/api/health")
    if status != 200:
        print(f"The stack is not reachable at {api.base_url} (HTTP {status}). Start it with: docker compose up --build -d")
        return 1
    if compose(docker, "ps", "--quiet", SERVICE).returncode != 0:
        print(f'Docker Compose is not available as "{args.compose}" (see --compose).')
        return 1
    admin = api.login(env["BOOTSTRAP_ADMIN_EMAIL"], env["BOOTSTRAP_ADMIN_PASSWORD"])
    operator = api.login(env["BOOTSTRAP_OPERATOR_EMAIL"], env["BOOTSTRAP_OPERATOR_PASSWORD"])

    rec = Recorder()
    began = datetime.now(timezone.utc)
    print(f"VigilOps failed-remediation demonstration against {api.base_url}")
    try:
        run(api, admin, operator, rec, docker)
    finally:
        compose(docker, "start", SERVICE)  # never leave the application stopped

    passed = len(rec.checks) - rec.failed
    print(f"\nRESULT: {passed} passed, {rec.failed} failed, {len(rec.checks)} checks")
    if not args.no_save:
        out = ROOT / "docs" / "evidence" / "failed-remediation.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "started_at": began.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "base_url": api.base_url,
                    "version": health.get("version"),
                    "environment": health.get("environment"),
                    "scenario": "The monitored application's container is stopped; ACTION-001 cannot reach its recovery endpoint.",
                    "passed": passed,
                    "failed": rec.failed,
                    "measurements": rec.measurements,
                    "checks": rec.checks,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Evidence written to {out.relative_to(ROOT)}")
    return 0 if rec.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
