"""Central application configuration.

All configuration is read from environment variables (optionally via a ``.env``
file).  Nothing secret has a default value in source code: ``SECRET_KEY``,
``DATABASE_URL`` and ``ALERT_WEBHOOK_TOKEN`` must be provided explicitly.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Values that ship in .env.example.  They are acceptable for a local
# development stack but are rejected when ENVIRONMENT=production.
_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "example", "dev-only")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


# Password policy.  Defined here (not in core.security, which imports this
# module) so that the configuration check and the API enforce the same rule.
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 72  # bcrypt limit


def password_problem(password: str) -> Optional[str]:
    """Return a human-readable problem, or None when the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password must be at most {MAX_PASSWORD_BYTES} bytes long."
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        return "Password must contain both upper-case and lower-case letters."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Identity -----------------------------------------------------
    PROJECT_NAME: str = "VigilOps"
    PROJECT_TITLE: str = "VigilOps: Secure Cloud Operations"
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"  # development | production | test
    # "api" (default) or "worker".  The worker neither signs tokens nor receives
    # webhooks, so it is not given SECRET_KEY or ALERT_WEBHOOK_TOKEN at all.
    PROCESS_ROLE: str = "api"

    # --- Security -----------------------------------------------------
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    CORS_ORIGINS: str = ""  # comma separated; empty = same-origin only
    ENABLE_API_DOCS: Optional[bool] = None  # default: on in development, off in production

    # --- Database -----------------------------------------------------
    DATABASE_URL: str
    # Apply the Alembic migrations inside the API process when it starts.  The
    # Compose image runs "alembic upgrade head" as a separate step instead; the
    # single-container image uses this to avoid starting a second interpreter.
    RUN_MIGRATIONS_ON_START: bool = False

    # --- Bootstrap accounts (created only when missing) ----------------
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    BOOTSTRAP_OPERATOR_EMAIL: str = ""
    BOOTSTRAP_OPERATOR_PASSWORD: str = ""

    # --- Integrated services ------------------------------------------
    PROMETHEUS_URL: str = "http://localhost:9090"
    ALERTMANAGER_URL: str = "http://localhost:9093"
    DEMO_APP_URL: str = "http://localhost:8001"
    DEMO_APP_JOB: str = "demo-app"
    BACKEND_JOB: str = "vigilops-backend"
    MONITORING_HTTP_TIMEOUT_SECONDS: float = 4.0
    PROMETHEUS_SCRAPE_INTERVAL_SECONDS: int = 5
    # Must equal repeat_interval in monitoring/alertmanager.yml (used to detect a stale alert signal).
    ALERT_REPEAT_INTERVAL_SECONDS: int = 120

    # Token Alertmanager must present on the incident webhook.
    ALERT_WEBHOOK_TOKEN: str = ""

    # --- Demonstration environment ------------------------------------
    # Demo controls (fault injection, sample-config reset) are refused in
    # production regardless of this flag.
    DEMO_CONTROLS_ENABLED: bool = False
    DEMO_APP_CONTROL_TOKEN: str = ""   # backend -> demo app fault injection
    DEMO_APP_RECOVERY_TOKEN: str = ""  # worker  -> demo app recovery (ACTION-001)

    # --- Hosted demonstration profile ----------------------------------
    # A public demonstration instance runs with ENVIRONMENT=production (every
    # production safeguard applies) but exists to show the demo.  This explicit
    # opt-in keeps the Administrator-only demo controls available there.  It must
    # stay false on any instance that monitors a real workload.
    ALLOW_DEMO_CONTROLS_IN_PRODUCTION: bool = False
    # Comma-separated fault modes that are not offered, for hosts that cannot
    # survive them (for example "cpu,memory" on a small shared instance).
    DEMO_DISABLED_FAULTS: str = ""
    # Answer /metrics and /health/ready only to callers on the loopback interface.
    # Needed when the API port itself is the public port (no reverse proxy in
    # front that withholds those paths).
    INTERNAL_ENDPOINTS_LOCAL_ONLY: bool = False

    # --- Security scanner ---------------------------------------------
    SECURITY_RULES_DIR: str = str(REPO_ROOT / "security-rules")
    SCAN_WORKSPACE_DIR: str = str(REPO_ROOT / ".runtime" / "scan-workspace")
    SCAN_MAX_FILE_BYTES: int = 262_144
    # Files inside the scan workspace that ACTION-002 is allowed to modify.
    REMEDIATION_WRITABLE_TARGETS: str = "cloud-infrastructure.yaml"

    # --- Remediation worker -------------------------------------------
    WORKER_ID: str = "remediation-worker-1"
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_HEARTBEAT_SECONDS: float = 10.0
    ACTION_TIMEOUT_SECONDS: float = 30.0
    VERIFY_TIMEOUT_SECONDS: float = 150.0
    REMEDIATION_MAX_ATTEMPTS: int = 3

    # --- VigilAI --------------------------------------------------------
    AI_PROVIDER: str = "gemini"  # gemini | none
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    AI_TIMEOUT_SECONDS: float = 20.0
    AI_MAX_OUTPUT_TOKENS: int = 800
    AI_MAX_INPUT_CHARS: int = 1000
    AI_MAX_HISTORY_TURNS: int = 6
    AI_RATE_LIMIT_PER_MINUTE: int = 10
    AI_DAILY_REQUEST_LIMIT: int = 400  # 0 disables the daily cap
    KNOWLEDGE_BASE_DIR: str = str(REPO_ROOT / "knowledge_base")

    # --- Logging --------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | text

    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        env = self.ENVIRONMENT.lower()
        if env not in {"development", "production", "test"}:
            raise ValueError("ENVIRONMENT must be development, production or test")
        self.ENVIRONMENT = env

        self.PROCESS_ROLE = self.PROCESS_ROLE.lower().strip()
        if self.PROCESS_ROLE not in {"api", "worker"}:
            raise ValueError("PROCESS_ROLE must be 'api' or 'worker'")
        if self.PROCESS_ROLE == "api":
            # No defaults exist in code: the API refuses to start without real values.
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be set and at least 32 characters long")
            if len(self.ALERT_WEBHOOK_TOKEN) < 16:
                raise ValueError("ALERT_WEBHOOK_TOKEN must be set and at least 16 characters long")

        if env == "production":
            weak = [
                name
                for name in (
                    "SECRET_KEY",
                    "ALERT_WEBHOOK_TOKEN",
                    "BOOTSTRAP_ADMIN_PASSWORD",
                    "BOOTSTRAP_OPERATOR_PASSWORD",
                    "DEMO_APP_RECOVERY_TOKEN",
                    "DEMO_APP_CONTROL_TOKEN",
                )
                if getattr(self, name) and _looks_like_placeholder(getattr(self, name))
            ]
            database_password = re.search(r"://[^:/@]+:([^@]+)@", self.DATABASE_URL)
            if database_password and _looks_like_placeholder(database_password.group(1)):
                weak.append("DATABASE_URL (database password)")
            if weak:
                raise ValueError(
                    "Refusing to start in production with placeholder values for: "
                    + ", ".join(weak)
                )
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite is not supported in production; use PostgreSQL")
            # A bootstrap password that fails the password policy would be skipped at
            # start-up, leaving an instance nobody can sign in to.  Refuse to start instead.
            if self.PROCESS_ROLE == "api":
                for name in ("BOOTSTRAP_ADMIN_PASSWORD", "BOOTSTRAP_OPERATOR_PASSWORD"):
                    problem = password_problem(getattr(self, name))
                    if getattr(self, name) and problem:
                        raise ValueError(f"{name} does not meet the password policy: {problem}")

        self.AI_PROVIDER = self.AI_PROVIDER.lower().strip()
        if self.AI_PROVIDER not in {"gemini", "none"}:
            raise ValueError("AI_PROVIDER must be 'gemini' or 'none'")
        return self

    # ------------------------------------------------------------------
    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL with an explicit driver.

        A bare ``postgresql://`` URL would let SQLAlchemy pick its default
        driver, which differs between SQLAlchemy versions; this project ships
        psycopg2, so the driver is pinned here.
        """
        url = self.DATABASE_URL
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg2://" + url[len(prefix):]
        return url

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def demo_controls_active(self) -> bool:
        """Demo controls are off in production mode unless explicitly allowed
        for a hosted demonstration instance (ALLOW_DEMO_CONTROLS_IN_PRODUCTION)."""
        if not self.DEMO_CONTROLS_ENABLED:
            return False
        return not self.is_production or self.ALLOW_DEMO_CONTROLS_IN_PRODUCTION

    @property
    def disabled_fault_modes(self) -> List[str]:
        """Fault modes switched off for this deployment ("none" can never be disabled)."""
        modes = {m.strip().lower() for m in self.DEMO_DISABLED_FAULTS.split(",") if m.strip()}
        return sorted(modes - {"none"})

    @property
    def api_docs_enabled(self) -> bool:
        if self.ENABLE_API_DOCS is None:
            return not self.is_production
        return self.ENABLE_API_DOCS

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def writable_target_names(self) -> List[str]:
        return [t.strip() for t in self.REMEDIATION_WRITABLE_TARGETS.split(",") if t.strip()]

    @property
    def scan_workspace_path(self) -> Path:
        return Path(self.SCAN_WORKSPACE_DIR).resolve()

    @property
    def security_rules_path(self) -> Path:
        return Path(self.SECURITY_RULES_DIR).resolve()

    @property
    def knowledge_base_path(self) -> Path:
        return Path(self.KNOWLEDGE_BASE_DIR).resolve()

    @property
    def ai_configured(self) -> bool:
        return self.AI_PROVIDER == "gemini" and bool(self.GEMINI_API_KEY.strip())

    def uses_placeholder_secrets(self) -> bool:
        return _looks_like_placeholder(self.SECRET_KEY) or _looks_like_placeholder(
            self.ALERT_WEBHOOK_TOKEN
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
