"""Allowlisted remediation actions (execution phase).

There is exactly one hard-coded handler per action code.  Handlers receive a
small, typed parameter object built by the worker from database records -
never free text from a user or from the AI assistant - and they perform a
single narrowly scoped operation:

* ACTION-001 calls one token-protected HTTP endpoint on the demo application.
* ACTION-002 edits one allowlisted YAML file inside the scan workspace.

No handler runs a shell command, touches the Docker daemon or accesses any
path outside the scan workspace.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml

from app.core.config import settings
from app.security_scanner.engine import ScanInputError, parse_yaml_document
from app.security_scanner.rules import PUBLIC_ACLS
from app.services.remediation_catalog import (
    ACTION_FIX_PUBLIC_STORAGE,
    ACTION_RECOVER_APP,
    ACTIONS,
)
from app.services.scan_service import ScanTargetError, resolve_target


class ActionError(RuntimeError):
    """The action could not be carried out.  ``retryable`` marks transient causes."""

    def __init__(self, message: str, *, retryable: bool = False, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.details = details or {}


@dataclass(frozen=True)
class ActionParams:
    request_id: int
    action_code: str
    # ACTION-001
    alert_name: Optional[str] = None
    # ACTION-002
    target_file: Optional[str] = None
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# ACTION-001  Recover the monitored demonstration application
# ---------------------------------------------------------------------------
RECOVERY_ATTEMPTS = 3


def probe_readiness(timeout: float = 3.0) -> Dict[str, Any]:
    """One readiness probe against the demo application."""
    try:
        response = httpx.get(f"{settings.DEMO_APP_URL}/health/ready", timeout=timeout)
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = None
        return {
            "reachable": True,
            "status_code": response.status_code,
            "ready": response.status_code == 200,
            "body": body,
            "observed_at": _now_iso(),
        }
    except httpx.HTTPError as exc:
        return {
            "reachable": False,
            "status_code": None,
            "ready": False,
            "error": exc.__class__.__name__,
            "observed_at": _now_iso(),
        }


def recover_demo_application(params: ActionParams) -> Dict[str, Any]:
    if not settings.DEMO_APP_RECOVERY_TOKEN:
        raise ActionError("The worker has no recovery token configured (DEMO_APP_RECOVERY_TOKEN).")

    before = probe_readiness()
    calls: List[Dict[str, Any]] = []
    response_body: Any = None
    succeeded = False

    for attempt in range(1, RECOVERY_ATTEMPTS + 1):
        entry: Dict[str, Any] = {"attempt": attempt, "at": _now_iso()}
        try:
            response = httpx.post(
                f"{settings.DEMO_APP_URL}/internal/recover",
                headers={"Authorization": f"Bearer {settings.DEMO_APP_RECOVERY_TOKEN}"},
                timeout=5.0,
            )
            entry["status_code"] = response.status_code
            calls.append(entry)
            if response.status_code == 200:
                try:
                    response_body = response.json()
                except ValueError:
                    response_body = None
                succeeded = True
                break
            if response.status_code in (401, 403, 404):
                # Not transient: retrying an authorisation failure is pointless.
                raise ActionError(
                    f"The application rejected the recovery call (HTTP {response.status_code}).",
                    details={"before": before, "recovery_calls": calls},
                )
        except httpx.HTTPError as exc:
            entry["error"] = exc.__class__.__name__
            calls.append(entry)
        if attempt < RECOVERY_ATTEMPTS:
            time.sleep(attempt)  # 1s, 2s back-off; the call is idempotent so retrying is safe

    if not succeeded:
        raise ActionError(
            f"The recovery endpoint could not be reached after {RECOVERY_ATTEMPTS} attempts.",
            retryable=True,
            details={"before": before, "recovery_calls": calls},
        )
    return {
        "action": ACTION_RECOVER_APP,
        "operation": "POST /internal/recover on the demonstration application",
        "before": before,
        "recovery_calls": calls,
        "response": response_body,
        "recovered_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# ACTION-002  Correct public storage configuration
# ---------------------------------------------------------------------------
def _leading_comments(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    return "".join(lines)


def render_document(document: Dict[str, Any], header: str = "") -> str:
    body = yaml.safe_dump(document, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return header + body


def atomic_write(path: Path, content: str) -> None:
    """Write via a temporary file in the same directory, then rename over the target."""
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".vigilops-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def resolve_writable_target(name: str) -> Path:
    if name not in settings.writable_target_names:
        raise ActionError(f"'{name}' is not on the remediation allowlist.")
    try:
        return resolve_target(name)
    except ScanTargetError as exc:
        raise ActionError(str(exc)) from exc


def fix_public_storage(params: ActionParams) -> Dict[str, Any]:
    if not params.target_file or not params.resource_name or params.resource_type != "storage_bucket":
        raise ActionError("ACTION-002 requires a storage bucket finding as its source.")

    path = resolve_writable_target(params.target_file)
    try:
        if path.stat().st_size > settings.SCAN_MAX_FILE_BYTES:
            raise ActionError(f"The configuration file is larger than {settings.SCAN_MAX_FILE_BYTES} bytes.")
        original = path.read_text(encoding="utf-8")
        document = parse_yaml_document(original, source=params.target_file)
    except (OSError, UnicodeDecodeError) as exc:
        raise ActionError(f"The configuration file cannot be read: {exc.__class__.__name__}") from exc
    except ScanInputError as exc:
        raise ActionError(f"The configuration file is not valid: {exc}") from exc

    resource = next(
        (
            item
            for item in document["resources"]
            if item["type"] == "storage_bucket" and item["name"] == params.resource_name
        ),
        None,
    )
    if resource is None:
        raise ActionError(
            f"Bucket '{params.resource_name}' no longer exists in {params.target_file}."
        )

    before = {"public_access": resource.get("public_access"), "acl": resource.get("acl")}
    changes: List[str] = []
    acl_is_public = str(resource.get("acl", "")).strip().lower() in PUBLIC_ACLS
    if resource.get("public_access") is True or (acl_is_public and "public_access" not in resource):
        resource["public_access"] = False
        changes.append("public_access: false")
    if acl_is_public:
        resource["acl"] = "private"
        changes.append("acl: private")
    after = {"public_access": resource.get("public_access"), "acl": resource.get("acl")}

    updated = original
    if changes:
        updated = render_document(document, _leading_comments(original))
        try:
            atomic_write(path, updated)
        except OSError as exc:
            raise ActionError(
                f"The configuration file could not be written: {exc.__class__.__name__}"
            ) from exc

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"{params.target_file} (before)",
            tofile=f"{params.target_file} (after)",
            n=2,
        )
    )
    return {
        "action": ACTION_FIX_PUBLIC_STORAGE,
        "operation": f"Edit {params.target_file} in the scan workspace",
        "target_file": params.target_file,
        "resource": f"storage_bucket/{params.resource_name}",
        "changed": bool(changes),
        "changes": changes or ["none - the bucket was already private (idempotent no-op)"],
        "before": before,
        "after": after,
        "sha256_before": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "sha256_after": hashlib.sha256(updated.encode("utf-8")).hexdigest(),
        "diff": diff[:6000],
        "completed_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
HANDLERS: Dict[str, Callable[[ActionParams], Dict[str, Any]]] = {
    ACTION_RECOVER_APP: recover_demo_application,
    ACTION_FIX_PUBLIC_STORAGE: fix_public_storage,
}

# The executable allowlist and the published catalog must be identical.
assert set(HANDLERS) == set(ACTIONS), "Action handlers do not match the remediation catalog"
