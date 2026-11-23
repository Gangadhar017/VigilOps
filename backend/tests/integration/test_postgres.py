"""PostgreSQL-only behaviour: migrations, append-only audit trail, legacy data, row locking.

These tests run only when TEST_DATABASE_URL points at PostgreSQL (CI runs the
suite once on SQLite and once on PostgreSQL).  Each test that needs a migrated
schema creates its own throw-away database, so the shared test schema that the
other tests use is never touched.
"""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.models import RemediationRequest, SecurityFinding, User
from app.workers import remediation_worker

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql", reason="requires PostgreSQL (set TEST_DATABASE_URL)"
)

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def scratch_database():
    """A fresh, empty database on the same server; dropped afterwards."""
    name = f"vigilops_mig_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(settings.sqlalchemy_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(settings.sqlalchemy_url).set(database=name)
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin_engine.dispose()


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")


def test_migration_creates_schema_matching_models(scratch_database):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.core.database import Base

    _upgrade(scratch_database)
    migrated = create_engine(scratch_database)
    with migrated.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        indexes = {index["name"] for index in inspect(connection).get_indexes("incidents")}
    migrated.dispose()
    assert differences == [], differences
    assert "uq_incidents_active_fingerprint" in indexes


def test_audit_events_are_append_only_at_database_level(scratch_database):
    _upgrade(scratch_database)
    migrated = create_engine(scratch_database)
    with migrated.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_events (event_id, actor_label, action, entity_type, outcome, metadata, created_at) "
                "VALUES (:id, 'tester', 'TEST_EVENT', 'test', 'SUCCESS', '{}', now())"
            ),
            {"id": str(uuid.uuid4())},
        )
    for statement in (
        "UPDATE audit_events SET action = 'TAMPERED'",
        "DELETE FROM audit_events",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            with migrated.begin() as connection:
                connection.execute(text(statement))
    with migrated.connect() as connection:
        assert connection.execute(text("SELECT action FROM audit_events")).scalar_one() == "TEST_EVENT"
    migrated.dispose()


def test_legacy_cloudshield_tables_are_preserved_not_dropped(scratch_database):
    """A database created by the old prototype keeps its data in a separate schema."""
    legacy = create_engine(scratch_database)
    with legacy.begin() as connection:
        connection.execute(text("CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255), role VARCHAR(50))"))
        connection.execute(text("CREATE INDEX ix_users_email ON users (email)"))
        connection.execute(text("CREATE TABLE resources (id SERIAL PRIMARY KEY, name VARCHAR(255))"))
        connection.execute(text("CREATE TABLE incidents (id SERIAL PRIMARY KEY, fingerprint VARCHAR(255), resource_id INTEGER REFERENCES resources(id), title VARCHAR(255))"))
        connection.execute(text("CREATE TABLE remediation_jobs (id SERIAL PRIMARY KEY, incident_id INTEGER REFERENCES incidents(id), requested_by INTEGER REFERENCES users(id))"))
        connection.execute(text("CREATE TABLE audit_logs (id SERIAL PRIMARY KEY, actor_email VARCHAR(255), action VARCHAR(100))"))
        connection.execute(text("INSERT INTO users (email, password_hash, role) VALUES ('old-admin@cloudshield.local', 'x', 'admin')"))
        connection.execute(text("INSERT INTO resources (name) VALUES ('test-app-service')"))
        connection.execute(text("INSERT INTO incidents (fingerprint, resource_id, title) VALUES ('fp', 1, 'Old incident')"))
        connection.execute(text("INSERT INTO audit_logs (actor_email, action) VALUES ('old-admin@cloudshield.local', 'SYSTEM_SEEDED')"))

    _upgrade(scratch_database)

    with legacy.connect() as connection:
        inspector = inspect(connection)
        assert {"users", "resources", "incidents", "remediation_jobs", "audit_logs"} <= set(
            inspector.get_table_names(schema="legacy_cloudshield")
        )
        assert connection.execute(text("SELECT email FROM legacy_cloudshield.users")).scalar_one() == "old-admin@cloudshield.local"
        assert connection.execute(text("SELECT title FROM legacy_cloudshield.incidents")).scalar_one() == "Old incident"
        assert connection.execute(text("SELECT count(*) FROM legacy_cloudshield.audit_logs")).scalar_one() == 1
        # The new schema is created alongside and starts empty.
        assert connection.execute(text("SELECT count(*) FROM public.users")).scalar_one() == 0
        assert "remediation_requests" in inspector.get_table_names(schema="public")
        assert "remediation_jobs" not in inspector.get_table_names(schema="public")
    legacy.dispose()


def test_two_workers_cannot_claim_the_same_request(db, workspace, admin, operator):
    """FOR UPDATE SKIP LOCKED: a request being claimed is invisible to a second worker."""
    finding = SecurityFinding(
        stable_finding_key="k" * 64, rule_id="SEC-001", rule_name="Public Storage Access", severity="HIGH",
        target_file="cloud-infrastructure.yaml", resource_type="storage_bucket", resource_name="customer-records",
        resource_identifier="storage_bucket/customer-records", status="REMEDIATION_PENDING",
    )
    db.add(finding)
    db.flush()
    request = RemediationRequest(
        source_type="finding", finding_id=finding.id, action_code="ACTION-002", target="t",
        requested_by=operator.id, approved_by=admin.id, status="QUEUED", justification="row locking test",
    )
    db.add(request)
    db.commit()

    first, second = SessionLocal(), SessionLocal()
    try:
        from sqlalchemy import select

        statement = (
            select(RemediationRequest)
            .where(RemediationRequest.status == "QUEUED")
            .with_for_update(skip_locked=True, of=RemediationRequest)
        )
        locked = first.execute(statement).scalars().all()  # worker 1 holds the row lock
        assert [r.id for r in locked] == [request.id]
        assert second.execute(statement).scalars().all() == []  # worker 2 skips it instead of blocking
        assert remediation_worker.claim_next(second) is None
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()

    assert remediation_worker.claim_next(db) is not None  # free again once the first worker lets go
    assert db.get(User, admin.id) is not None
