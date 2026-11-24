#!/usr/bin/env python3
"""Start and supervise every VigilOps component inside one container.

Used by deploy/render/Dockerfile, the image for hosts that give you a single
small web service (see docs/deployment-render-vercel.md).  The Compose stack
does not use this file.

What it does, in order:

1. checks that the required settings are present,
2. creates the runtime directories with the right owners (the scan workspace
   is writable by the worker only and readable by the API's group),
3. writes the monitoring configuration - the version-controlled files from
   monitoring/ with the Compose host names replaced by 127.0.0.1,
4. starts the API first (it applies the database migrations and then opens
   the public port), then the demonstration application, the worker,
   Alertmanager and - last, once its scrape targets answer - Prometheus,
5. restarts a component that exits, and stops the container if one keeps
   failing, so that the platform's own restart policy takes over.

Each component runs as its own unprivileged user and receives only the
environment variables it needs: the API never sees the recovery token, the
worker never sees SECRET_KEY, the Gemini key or the webhook token, and the
monitoring processes see no secret at all (Alertmanager reads the webhook
token from a file only it can read).

If the host does not let the container switch users (it is not started as
root, or the SETUID / SETGID / CHOWN capabilities are missing), everything
runs as the current user instead.  The platform then works the same, but the
per-user separation is not in effect; the log says so clearly.

Standard library only.
"""
from __future__ import annotations

import grp
import os
import pwd
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path("/srv/vigilops")
BACKEND_DIR = ROOT / "backend"
MONITORING_DIR = ROOT / "monitoring"

API_PORT = int(os.environ.get("PORT", "10000"))
DEMO_APP_PORT = 8001
PROMETHEUS_PORT = 9090
ALERTMANAGER_PORT = 9093

REQUIRED = ("DATABASE_URL", "SECRET_KEY", "ALERT_WEBHOOK_TOKEN")

# --- which component may see which setting ---------------------------------
RUNTIME = ("PATH", "LANG", "LC_ALL", "TZ", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE")
SHARED = (
    "ENVIRONMENT", "DATABASE_URL", "DEMO_CONTROLS_ENABLED", "ALLOW_DEMO_CONTROLS_IN_PRODUCTION",
    "DEMO_DISABLED_FAULTS", "PROMETHEUS_SCRAPE_INTERVAL_SECONDS", "ALERT_REPEAT_INTERVAL_SECONDS",
    "MONITORING_HTTP_TIMEOUT_SECONDS", "REMEDIATION_WRITABLE_TARGETS", "REMEDIATION_MAX_ATTEMPTS",
    "ACTION_TIMEOUT_SECONDS", "VERIFY_TIMEOUT_SECONDS", "SCAN_MAX_FILE_BYTES", "LOG_LEVEL", "LOG_FORMAT",
    "KNOWLEDGE_BASE_DIR", "SECURITY_RULES_DIR",
)
API_ONLY = (
    "SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "ALERT_WEBHOOK_TOKEN", "DEMO_APP_CONTROL_TOKEN",
    "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD", "BOOTSTRAP_OPERATOR_EMAIL", "BOOTSTRAP_OPERATOR_PASSWORD",
    "AI_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL", "AI_TIMEOUT_SECONDS", "AI_MAX_OUTPUT_TOKENS",
    "AI_RATE_LIMIT_PER_MINUTE", "AI_DAILY_REQUEST_LIMIT", "LOGIN_RATE_LIMIT_ATTEMPTS",
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS", "CORS_ORIGINS", "ENABLE_API_DOCS", "INTERNAL_ENDPOINTS_LOCAL_ONLY",
    "SERVE_DEMO_APP",
)
WORKER_ONLY = ("DEMO_APP_RECOVERY_TOKEN", "WORKER_ID", "WORKER_POLL_INTERVAL_SECONDS", "WORKER_HEARTBEAT_SECONDS")
DEMO_APP_ONLY = (
    "DEMO_CONTROLS_ENABLED", "DEMO_APP_CONTROL_TOKEN", "DEMO_APP_RECOVERY_TOKEN", "DEMO_DISABLED_FAULTS",
    "LOAD_GENERATOR_ENABLED", "LOAD_INTERVAL_SECONDS",
)

INTERNAL_URLS = {
    "PROMETHEUS_URL": f"http://127.0.0.1:{PROMETHEUS_PORT}",
    "ALERTMANAGER_URL": f"http://127.0.0.1:{ALERTMANAGER_PORT}",
    "DEMO_APP_URL": f"http://127.0.0.1:{DEMO_APP_PORT}",
}

MAX_RESTARTS = 5              # of one component ...
RESTART_WINDOW_SECONDS = 300  # ... within this window, before the container gives up


def log(message: str) -> None:
    print(f"[launcher] {message}", flush=True)


def pick(*groups) -> Dict[str, str]:
    """Environment made of exactly the named variables that are set."""
    names = [name for group in groups for name in group]
    return {name: os.environ[name] for name in names if os.environ.get(name) not in (None, "")}


def can_switch_users() -> bool:
    """May this process change file ownership and start processes as other users?"""
    if os.geteuid() != 0:
        return False
    probe = Path("/tmp/.vigilops-privilege-probe")
    try:
        user = pwd.getpwnam("monitoring")
        probe.write_text("probe", encoding="utf-8")
        os.chown(probe, user.pw_uid, user.pw_gid)
        subprocess.run(["true"], user=user.pw_uid, group=user.pw_gid, extra_groups=[], check=True)
        return True
    except (KeyError, OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


class Layout:
    """Where the runtime files live, and whether components get their own users."""

    def __init__(self, separate_users: bool) -> None:
        self.separate_users = separate_users
        if separate_users:
            self.run_dir = Path("/run/vigilops")
            self.state_dir = Path("/var/lib/vigilops")
            self.workspace = Path(os.environ.get("SCAN_WORKSPACE_DIR", "/data/scan-workspace"))
        else:
            base = Path("/tmp/vigilops")
            self.run_dir = base / "run"
            self.state_dir = base / "state"
            self.workspace = base / "scan-workspace"

    def owned_dir(self, path: Path, user: str, group: str, mode: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        if self.separate_users:
            os.chown(path, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid)
        os.chmod(path, mode)

    def prepare(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.run_dir, 0o755)
        # Worker owns the workspace; the API's group may list and read it, nothing more.
        # The set-group-id bit makes new files inherit that group.
        self.owned_dir(self.workspace, "vigilworker", "vigilops", 0o2750)
        self.owned_dir(self.state_dir / "prometheus", "monitoring", "monitoring", 0o750)
        self.owned_dir(self.state_dir / "alertmanager", "monitoring", "monitoring", 0o750)

        token_file = self.run_dir / "alert_webhook_token"
        token_file.write_text(os.environ["ALERT_WEBHOOK_TOKEN"], encoding="utf-8")
        if self.separate_users:
            monitoring = pwd.getpwnam("monitoring")
            os.chown(token_file, monitoring.pw_uid, monitoring.pw_gid)
        os.chmod(token_file, 0o400)

    def write_monitoring_config(self) -> None:
        rewrite(
            MONITORING_DIR / "prometheus.yml",
            self.run_dir / "prometheus.yml",
            {
                "/etc/prometheus/alert_rules.yml": str(MONITORING_DIR / "alert_rules.yml"),
                '"alertmanager:9093"': f'"127.0.0.1:{ALERTMANAGER_PORT}"',
                '"test-app:8001"': f'"127.0.0.1:{DEMO_APP_PORT}"',
                '"backend:8000"': f'"127.0.0.1:{API_PORT}"',
                '"localhost:9090"': f'"127.0.0.1:{PROMETHEUS_PORT}"',
            },
        )
        rewrite(
            MONITORING_DIR / "alertmanager.yml",
            self.run_dir / "alertmanager.yml",
            {
                "http://backend:8000/api/alerts/webhook": f"http://127.0.0.1:{API_PORT}/api/alerts/webhook",
                "/run/secrets/alert_webhook_token": str(self.run_dir / "alert_webhook_token"),
            },
        )


def rewrite(source: Path, target: Path, replacements: Dict[str, str]) -> None:
    """Copy a monitoring file, replacing Compose host names.  Every replacement
    must apply: if the source file changed shape, fail loudly instead of
    starting with a half-rewritten configuration."""
    text = source.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if old not in text:
            raise SystemExit(
                f"[launcher] {source.name}: expected to find '{old}' - the monitoring file changed; update launcher.py"
            )
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")
    os.chmod(target, 0o644)


class Component:
    def __init__(self, name: str, user: Optional[str], command: List[str], env: Dict[str, str], cwd: Path = ROOT,
                 ready_url: Optional[str] = None) -> None:
        self.name = name
        self.user = pwd.getpwnam(user) if user else None
        self.command = command
        self.env = {**env, "HOME": "/tmp"}
        self.cwd = cwd
        self.ready_url = ready_url
        self.process: Optional[subprocess.Popen] = None
        self.restarts: List[float] = []

    def start(self) -> None:
        identity = {}
        if self.user is not None:
            identity = {"user": self.user.pw_uid, "group": self.user.pw_gid, "extra_groups": []}
        self.process = subprocess.Popen(self.command, cwd=str(self.cwd), env=self.env, **identity)
        owner = self.user.pw_name if self.user is not None else "current user"
        log(f"started {self.name} (pid {self.process.pid}, {owner})")

    def wait_ready(self, timeout: float) -> bool:
        if not self.ready_url:
            return True
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(self.ready_url, timeout=3) as response:
                    if response.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.5)
        return False

    def stop(self, grace: float = 10.0) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def build_components(layout: Layout) -> List[Component]:
    def user(name: str) -> Optional[str]:
        return name if layout.separate_users else None

    paths = {"SCAN_WORKSPACE_DIR": str(layout.workspace)}
    # The API applies the database migrations itself before it starts serving:
    # a separate "alembic upgrade head" would start a second interpreter and
    # roughly double the time until the public port opens on a small CPU share.
    api_env = {
        **pick(RUNTIME, SHARED, API_ONLY), **INTERNAL_URLS, **paths,
        "PROCESS_ROLE": "api", "RUN_MIGRATIONS_ON_START": "true",
    }
    worker_env = {**pick(RUNTIME, SHARED, WORKER_ONLY), **INTERNAL_URLS, **paths, "PROCESS_ROLE": "worker"}
    demo_env = {**pick(RUNTIME, DEMO_APP_ONLY), "PORT": str(DEMO_APP_PORT), "HOST": "127.0.0.1"}
    # Go processes: one scheduler thread and a soft memory limit keep them small.
    go_env = {**pick(RUNTIME), "GOMAXPROCS": "1"}

    return [
        Component(
            "api", user("vigilops"),
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(API_PORT),
             "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", os.environ.get("FORWARDED_ALLOW_IPS", "*")],
            api_env, cwd=BACKEND_DIR, ready_url=f"http://127.0.0.1:{API_PORT}/health/live",
        ),
        Component(
            "demo-app", user("demoapp"), [sys.executable, str(ROOT / "test-app" / "app.py")],
            demo_env, ready_url=f"http://127.0.0.1:{DEMO_APP_PORT}/health/live",
        ),
        Component(
            "worker", user("vigilworker"), [sys.executable, "-m", "app.workers.remediation_worker"],
            worker_env, cwd=BACKEND_DIR,
        ),
        Component(
            "alertmanager", user("monitoring"),
            ["alertmanager", f"--config.file={layout.run_dir / 'alertmanager.yml'}",
             f"--storage.path={layout.state_dir / 'alertmanager'}",
             f"--web.listen-address=127.0.0.1:{ALERTMANAGER_PORT}",
             "--cluster.listen-address=", "--log.level=warn"],
            {**go_env, "GOMEMLIMIT": "40MiB"},
            ready_url=f"http://127.0.0.1:{ALERTMANAGER_PORT}/-/ready",
        ),
        Component(
            "prometheus", user("monitoring"),
            ["prometheus", f"--config.file={layout.run_dir / 'prometheus.yml'}",
             f"--storage.tsdb.path={layout.state_dir / 'prometheus'}", "--storage.tsdb.retention.time=1d",
             f"--web.listen-address=127.0.0.1:{PROMETHEUS_PORT}", "--log.level=warn"],
            {**go_env, "GOMEMLIMIT": "110MiB"},
            ready_url=f"http://127.0.0.1:{PROMETHEUS_PORT}/-/ready",
        ),
    ]


def main() -> int:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        log("missing required settings: " + ", ".join(missing))
        return 2

    layout = Layout(separate_users=can_switch_users())
    if not layout.separate_users:
        log(
            "WARNING: this host does not let the container switch users (not root, or the SETUID/SETGID/CHOWN "
            "capabilities are missing). Every component runs as the current user; the per-user separation "
            "described in docs/deployment-render-vercel.md is NOT in effect."
        )
    layout.prepare()
    layout.write_monitoring_config()
    components = build_components(layout)

    stopping = {"flag": False}

    def shutdown(_signum, _frame) -> None:
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    started = time.monotonic()
    for component in components:
        component.start()
        # Generous: the API may be waiting for a database that is still being created.
        if not component.wait_ready(timeout=420):
            log(f"{component.name} did not become ready; stopping")
            for other in reversed(components):
                other.stop()
            return 1
        if component.ready_url:
            log(f"{component.name} is ready ({time.monotonic() - started:.0f} s after launch)")
    log(f"all components running; API on port {API_PORT}")

    while not stopping["flag"]:
        time.sleep(1.0)
        for component in components:
            code = component.process.poll() if component.process else None
            if code is None:
                continue
            now = time.monotonic()
            component.restarts = [t for t in component.restarts if now - t < RESTART_WINDOW_SECONDS] + [now]
            log(f"{component.name} exited with code {code}")
            if len(component.restarts) > MAX_RESTARTS:
                log(f"{component.name} failed {len(component.restarts)} times in {RESTART_WINDOW_SECONDS} s; stopping the container")
                for other in reversed(components):
                    other.stop()
                return 1
            time.sleep(3.0)
            if not stopping["flag"]:
                component.start()

    log("stop requested; shutting the components down")
    for component in reversed(components):
        component.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
