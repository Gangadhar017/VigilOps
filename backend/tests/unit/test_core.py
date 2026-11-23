"""Core building blocks: passwords, tokens, rate limiting, redaction, settings."""
import logging

import pytest
from jose import jwt

from app.core.config import Settings
from app.core.logging import JsonFormatter, redact
from app.core.permissions import PERMISSIONS, permissions_for
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.models import User
from app.services.audit_service import sanitize_metadata

BASE_ENV = {
    "SECRET_KEY": "k" * 40,
    "DATABASE_URL": "postgresql://u:p@db/x",
    "ALERT_WEBHOOK_TOKEN": "t" * 24,
}


def test_password_hash_is_bcrypt_and_verifies():
    hashed = hash_password("Correct-Horse-1")
    assert hashed.startswith("$2") and "Correct-Horse-1" not in hashed
    assert verify_password("Correct-Horse-1", hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password("anything", None)  # unknown user: still constant work, never True


@pytest.mark.parametrize(
    "password, ok",
    [
        ("Short1a", False),
        ("alllowercase123", False),
        ("ALLUPPERCASE123", False),
        ("NoDigitsInHere", False),
        ("x" * 80 + "A1", False),
        ("Valid-Password-1", True),
    ],
)
def test_password_policy(password, ok):
    assert (validate_password_strength(password) is None) is ok


def test_access_token_roundtrip_and_tamper_detection():
    user = User(id=7, email="a@b.c", role="operator", token_version=3, password_hash="x")
    token, expires_at, jti = create_access_token(user)
    claims = decode_access_token(token)
    assert claims["sub"] == "7" and claims["role"] == "operator"
    assert claims["ver"] == 3 and claims["jti"] == jti and claims["exp"] == int(expires_at.timestamp())
    forged = jwt.encode({**claims, "role": "admin"}, "some-other-key-000000000000000000000", algorithm="HS256")
    with pytest.raises(Exception):
        decode_access_token(forged)


def test_sliding_window_limiter_blocks_and_recovers():
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=0.2)
    assert limiter.allow("k") == (True, 0)
    assert limiter.allow("k") == (True, 0)
    allowed, retry_after = limiter.allow("k")
    assert not allowed and retry_after >= 1
    assert limiter.allow("other")[0]  # keys are independent
    import time

    time.sleep(0.25)
    assert limiter.allow("k")[0]


def test_audit_metadata_never_contains_credentials():
    cleaned = sanitize_metadata(
        {"email": "a@b.c", "password": "hunter2", "nested": {"api_key": "AIza...", "ok": 1}, "Authorization": "Bearer x"}
    )
    assert cleaned == {
        "email": "a@b.c",
        "password": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]", "ok": 1},
        "Authorization": "[REDACTED]",
    }
    assert len(sanitize_metadata({"note": "x" * 5000})["note"]) < 700


def test_log_redaction_masks_keys_tokens_and_passwords():
    # Fake keys are assembled at runtime so that no key-shaped literal sits in the repository.
    fake_old = "AIza" + "SyA1234567890abcdefghijklmnopqrstu"
    fake_new = "AQ." + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3_-AbCdEfGhIj"
    text = redact(
        f"key={fake_old} password=hunter2 "
        "Authorization: Bearer abcdefghijklmnop.qrstuvwx "
        f"the provider said {fake_new} was rejected, and {fake_old} too"
    )
    assert "AIzaSy" not in text and "hunter2" not in text and "abcdefghijklmnop" not in text
    assert "Ab1Cd2Ef3" not in text and "was rejected" in text
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "token=supersecretvalue", (), None)
    assert "supersecretvalue" not in JsonFormatter().format(record)


def test_permission_matrix_separates_roles():
    operator, admin = set(permissions_for("operator")), set(permissions_for("admin"))
    assert admin == set(PERMISSIONS)
    for privileged in ("remediation:approve", "remediation:execute", "users:manage", "settings:manage",
                       "incidents:close", "findings:accept_risk", "demo:control", "audit:view_all"):
        assert privileged in admin and privileged not in operator
    for shared in ("remediation:request", "scans:run", "incidents:update", "assistant:use"):
        assert shared in operator


def test_settings_require_strong_secrets():
    with pytest.raises(Exception):
        Settings(_env_file=None, **{**BASE_ENV, "SECRET_KEY": "short"})
    with pytest.raises(Exception):
        Settings(_env_file=None, **{**BASE_ENV, "ALERT_WEBHOOK_TOKEN": "short"})


def test_production_rejects_placeholders_and_disables_demo_controls():
    with pytest.raises(Exception, match="placeholder"):
        Settings(_env_file=None, ENVIRONMENT="production", **{**BASE_ENV, "SECRET_KEY": "change-me-" + "x" * 40})
    with pytest.raises(Exception, match="SQLite"):
        Settings(_env_file=None, ENVIRONMENT="production", **{**BASE_ENV, "DATABASE_URL": "sqlite:///x.db"})
    production = Settings(_env_file=None, ENVIRONMENT="production", DEMO_CONTROLS_ENABLED=True, **BASE_ENV)
    assert production.demo_controls_active is False
    assert production.api_docs_enabled is False
    development = Settings(_env_file=None, ENVIRONMENT="development", DEMO_CONTROLS_ENABLED=True, **BASE_ENV)
    assert development.demo_controls_active is True
