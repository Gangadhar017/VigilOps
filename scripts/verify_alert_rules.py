#!/usr/bin/env python3
"""Exercise every Prometheus alert rule with its controlled fault, end to end.

    python scripts/verify_alert_rules.py              # errors, latency, cpu, memory
    python scripts/verify_alert_rules.py --only cpu

For each fault mode of the demo application the script

  1. injects the fault through the Administrator demo control,
  2. waits for the matching alert to open an incident (real Prometheus rule,
     real Alertmanager delivery),
  3. clears the fault, and
  4. waits for the incident to be resolved automatically by the monitoring
     signal (Alertmanager "resolved" notification), then closes it.

The outage rule (ApplicationUnavailable) is covered by run_e2e_demos.py, which
recovers it through the remediation workflow instead.

Needs a running stack with DEMO_CONTROLS_ENABLED=true.  Standard library only.
Results are written to docs/evidence/alert-rules.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_e2e_demos import ROOT, Api, load_env, wait_for  # noqa: E402

FAULTS = {
    "errors": "HighHttp5xxErrorRate",
    "latency": "HighApiLatency",
    "cpu": "HighCpuUsage",
    "memory": "HighMemoryUsage",
}
EVIDENCE_METRIC = {
    "errors": "error_rate_5xx",
    "latency": "latency_p95",
    "cpu": "cpu_usage",
    "memory": "memory_rss",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=sorted(FAULTS))
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    api = Api(f"http://localhost:{env.get('VIGILOPS_HTTP_PORT', '8080')}")
    admin = api.login(env["BOOTSTRAP_ADMIN_EMAIL"], env["BOOTSTRAP_ADMIN_PASSWORD"])
    api.call("POST", "/api/demo/faults", admin, {"mode": "none"})

    results = []
    failed = 0
    for mode, alert in FAULTS.items():
        if args.only and mode != args.only:
            continue
        print(f"\n=== fault '{mode}' -> expecting alert {alert} ===")
        # Leftovers of earlier runs must not be mistaken for a new incident.
        _, leftovers = api.call("GET", f"/api/incidents?q={alert}&status=RESOLVED&page_size=50", admin)
        for incident in leftovers["items"]:
            api.call("POST", f"/api/incidents/{incident['id']}/transition", admin, {"status": "CLOSED", "note": "Closed before alert-rule verification."})

        injected = time.monotonic()
        status, _ = api.call("POST", "/api/demo/faults", admin, {"mode": mode})
        if status != 200:
            print(f"  [FAIL] could not inject fault (HTTP {status})")
            failed += 1
            continue

        def opened():
            _, listing = api.call("GET", f"/api/incidents?active_only=true&q={alert}", admin)
            return next((i for i in listing["items"] if i["alert_name"] == alert), None)

        incident, waited = wait_for(opened, timeout=180, interval=2.0)
        entry = {"fault": mode, "alert": alert, "incident_opened": bool(incident)}
        if not incident:
            print(f"  [FAIL] no incident for {alert} within 180 s")
            failed += 1
            api.call("POST", "/api/demo/faults", admin, {"mode": "none"})
            results.append(entry)
            continue
        entry.update(
            fault_to_incident_seconds=round(time.monotonic() - injected, 1),
            severity=incident["severity"],
            labelled_simulated=incident["is_simulated"],
        )
        _, overview = api.call("GET", "/api/monitoring/overview", admin)
        demo = next(r for r in overview["resources"] if r["job"] == "demo-app")
        metric = demo["metrics"].get(EVIDENCE_METRIC[mode], {})
        entry["observed_metric"] = {"name": EVIDENCE_METRIC[mode], "value": metric.get("value"), "unit": metric.get("unit")}
        print(f"  [PASS] incident #{incident['id']} opened after {entry['fault_to_incident_seconds']} s "
              f"(severity {incident['severity']}, {EVIDENCE_METRIC[mode]} = {metric.get('value')})")

        cleared = time.monotonic()
        api.call("POST", "/api/demo/faults", admin, {"mode": "none"})

        def resolved():
            _, current = api.call("GET", f"/api/incidents/{incident['id']}", admin)
            return current if current["status"] == "RESOLVED" else None

        done, waited = wait_for(resolved, timeout=240, interval=3.0)
        entry["auto_resolved_by_monitoring"] = bool(done)
        if done:
            entry["clear_to_resolved_seconds"] = round(time.monotonic() - cleared, 1)
            entry["resolution_summary"] = done["resolution_summary"]
            print(f"  [PASS] resolved by the monitoring signal after {entry['clear_to_resolved_seconds']} s")
            api.call("POST", f"/api/incidents/{incident['id']}/transition", admin, {"status": "CLOSED", "note": "Alert-rule verification complete."})
        else:
            print("  [FAIL] incident was not resolved within 240 s of clearing the fault")
            failed += 1
        results.append(entry)

    api.call("POST", "/api/demo/faults", admin, {"mode": "none"})
    print(f"\nRESULT: {len(results) - failed} of {len(results)} alert rules verified")
    if not args.no_save and not args.only:
        out = ROOT / "docs" / "evidence" / "alert-rules.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"run_at": datetime.now(timezone.utc).isoformat(), "results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"Evidence written to {out.relative_to(ROOT)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
