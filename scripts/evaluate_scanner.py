#!/usr/bin/env python3
"""Measure the scanner against the version-controlled fixtures.

    cd backend && python ../scripts/evaluate_scanner.py

For every insecure fixture the expected (rule, resource) pairs are listed in
this file; the script reports how many were detected (true positives), how
many were missed (false negatives) and anything detected that was not expected
(false positives).  Every secure fixture must produce zero findings.

The script only reads files and prints JSON; it needs no running stack.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PROCESS_ROLE", "worker")          # no API secrets needed for an offline scan
os.environ.setdefault("DATABASE_URL", "sqlite://")        # never opened
os.environ.setdefault("SECURITY_RULES_DIR", str(ROOT / "security-rules"))

from app.security_scanner.engine import scan_file  # noqa: E402

SAMPLES = ROOT / "security-rules" / "samples"
MAX_BYTES = 262_144

EXPECTED = {
    "insecure/sec-001-public-storage.yaml": {("SEC-001", "storage_bucket/public-assets-bucket")},
    "insecure/sec-002-missing-encryption.yaml": {
        ("SEC-002", "storage_bucket/unencrypted-bucket"),
        ("SEC-002", "disk_volume/data-volume-without-encryption-block"),
        ("SEC-002", "database/orders-db-no-algorithm"),
    },
    "insecure/sec-003-wildcard-iam.yaml": {
        ("SEC-003", "iam_policy/full-admin-policy"),
        ("SEC-003", "iam_policy/service-wide-wildcard-policy"),
        ("SEC-003", "iam_policy/wildcard-resource-policy"),
    },
    "insecure/sec-004-open-ingress.yaml": {
        ("SEC-004", "security_group/ssh-open-to-world"),
        ("SEC-004", "security_group/wide-port-range-open"),
        ("SEC-004", "security_group/rdp-open-ipv6"),
    },
    "insecure/sec-005-privileged-container.yaml": {
        ("SEC-005", "container/privileged-agent"),
        ("SEC-005", "container/privileged-via-security-context"),
    },
    "baseline/cloud-infrastructure.yaml": {
        ("SEC-001", "storage_bucket/customer-records"),
        ("SEC-002", "storage_bucket/customer-records"),
        ("SEC-003", "iam_policy/app-deployer-role"),
        ("SEC-004", "security_group/web-sg"),
        ("SEC-005", "container/worker-agent"),
    },
}


def main() -> int:
    true_positives = false_negatives = false_positives = 0
    per_file = {}
    started = time.perf_counter()

    for relative, expected in EXPECTED.items():
        path = SAMPLES / relative
        detected = {(v.rule.id, v.resource_identifier) for v in scan_file(path, path.name, max_bytes=MAX_BYTES)}
        true_positives += len(detected & expected)
        false_negatives += len(expected - detected)
        false_positives += len(detected - expected)
        per_file[relative] = {
            "expected": len(expected),
            "detected": len(detected & expected),
            "missed": sorted(map(list, expected - detected)),
            "unexpected": sorted(map(list, detected - expected)),
        }

    secure_files = sorted((SAMPLES / "secure").glob("*.yaml"))
    secure_resources = 0
    secure_false_positives = 0
    for path in secure_files:
        findings = scan_file(path, path.name, max_bytes=MAX_BYTES)
        secure_false_positives += len(findings)
        per_file[f"secure/{path.name}"] = {"expected": 0, "findings": len(findings)}
        import yaml

        secure_resources += len(yaml.safe_load(path.read_text(encoding="utf-8"))["resources"])

    # Determinism: 20 repeated scans of the baseline must give identical results.
    baseline = SAMPLES / "baseline" / "cloud-infrastructure.yaml"
    runs = {tuple(sorted((v.stable_key, v.summary) for v in scan_file(baseline, baseline.name, max_bytes=MAX_BYTES))) for _ in range(20)}

    elapsed_ms = (time.perf_counter() - started) * 1000
    expected_total = true_positives + false_negatives
    result = {
        "insecure_expected_violations": expected_total,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives_on_insecure_files": false_positives,
        "detection_rate": round(true_positives / expected_total, 4) if expected_total else None,
        "secure_fixture_files": len(secure_files),
        "secure_fixture_resources": secure_resources,
        "false_positives_on_secure_fixtures": secure_false_positives,
        "deterministic_over_20_runs": len(runs) == 1,
        "total_runtime_ms": round(elapsed_ms, 1),
        "per_file": per_file,
    }
    print(json.dumps(result, indent=2))
    ok = false_negatives == 0 and false_positives == 0 and secure_false_positives == 0 and len(runs) == 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
