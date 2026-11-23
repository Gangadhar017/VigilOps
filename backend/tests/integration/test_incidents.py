"""Alert webhook, deterministic deduplication and the incident lifecycle."""
from datetime import timedelta

from app.core.database import utcnow
from app.models.models import Incident, IncidentEvent
from tests.conftest import WEBHOOK_HEADERS, alert_payload, audit_actions, fire_alert


def _incidents(client, headers, **params):
    return client.get("/api/incidents", params=params, headers=headers).json()


def test_webhook_requires_the_shared_token(client, db, admin_headers):
    payload = alert_payload()
    assert client.post("/api/alerts/webhook", json=payload).status_code == 401
    assert client.post("/api/alerts/webhook", json=payload, headers={"Authorization": "Bearer wrong"}).status_code == 401
    # A valid *user* token is not a webhook credential.
    assert client.post("/api/alerts/webhook", json=payload, headers=admin_headers).status_code == 401
    assert db.query(Incident).count() == 0


def test_invalid_webhook_payloads_are_rejected(client, db):
    bad_payloads = [
        {},
        {"alerts": []},
        {"alerts": [{"status": "exploding", "labels": {"alertname": "X"}}]},
        {"alerts": [{"status": "firing", "labels": {}}]},
        {"alerts": [{"status": "firing", "labels": {"alertname": "X"}, "fingerprint": "not hex!"}]},
        {"alerts": "nope"},
    ]
    for payload in bad_payloads:
        assert client.post("/api/alerts/webhook", json=payload, headers=WEBHOOK_HEADERS).status_code == 422, payload
    assert db.query(Incident).count() == 0


def test_firing_alert_creates_an_incident(client, db, demo_resource, operator_headers):
    result = fire_alert(client)
    assert result["results"]["created"] == 1
    listing = _incidents(client, operator_headers)
    assert listing["total"] == 1
    incident = listing["items"][0]
    assert incident["status"] == "OPEN" and incident["severity"] == "CRITICAL"
    assert incident["alert_name"] == "ApplicationUnavailable"
    assert incident["affected_resource"] == "demo-app"
    assert incident["alert_fingerprint"] == "a1b2c3d4e5f60718"
    assert incident["action_code"] == "ACTION-001"
    assert incident["occurrence_count"] == 1 and incident["alert_active"] is True

    detail = client.get(f"/api/incidents/{incident['id']}", headers=operator_headers).json()
    assert detail["events"][0]["event_type"] == "ALERT_RECEIVED"
    assert detail["recommendation"]["automation"]["supported"] is True
    assert detail["recommendation"]["possible_causes"] and detail["recommendation"]["recommended_steps"]
    assert "INCIDENT_CREATED" in audit_actions(db)


def test_repeated_notifications_update_the_same_incident(client, db, demo_resource, operator_headers):
    for _ in range(4):
        fire_alert(client)
    assert db.query(Incident).count() == 1
    incident = db.query(Incident).one()
    assert incident.occurrence_count == 4
    # Repeats collapse into one timeline entry instead of flooding the timeline.
    assert db.query(IncidentEvent).filter(IncidentEvent.event_type == "ALERT_REPEATED").count() == 1
    assert audit_actions(db).count("INCIDENT_CREATED") == 1


def test_different_alerts_create_separate_incidents(client, db, demo_resource):
    fire_alert(client, fingerprint="aaaaaaaaaaaaaaaa")
    fire_alert(client, alertname="HighApiLatency", fingerprint="bbbbbbbbbbbbbbbb", severity="medium")
    assert db.query(Incident).count() == 2
    assert {i.severity for i in db.query(Incident)} == {"CRITICAL", "MEDIUM"}


def test_resolved_alert_resolves_incident_with_monitoring_evidence(client, db, demo_resource, operator_headers):
    fire_alert(client)
    result = fire_alert(client, status="resolved")
    assert result["results"]["resolved"] == 1
    incident = db.query(Incident).one()
    assert incident.status == "RESOLVED" and incident.resolved_at is not None
    assert incident.alert_active is False
    resolved_event = [e for e in incident.events if e.event_type == "RESOLVED"][0]
    assert resolved_event.event_metadata["evidence"]["source"] == "alertmanager"
    assert "INCIDENT_RESOLVED" in audit_actions(db)
    # A resolved notification for something we never tracked is ignored.
    assert fire_alert(client, status="resolved", fingerprint="cccccccccccccccc")["results"]["ignored"] == 1


def test_alert_refiring_inside_window_reopens_instead_of_duplicating(client, db, demo_resource):
    fire_alert(client)
    fire_alert(client, status="resolved")
    assert fire_alert(client)["results"]["reopened"] == 1
    assert db.query(Incident).count() == 1
    assert db.query(Incident).one().status == "OPEN"


def test_alert_refiring_after_window_or_close_creates_new_incident(client, db, demo_resource, admin_headers):
    fire_alert(client)
    fire_alert(client, status="resolved")
    first = db.query(Incident).one()
    first.resolved_at = utcnow() - timedelta(hours=3)  # outside the reopen window
    db.commit()
    assert fire_alert(client)["results"]["created"] == 1
    assert db.query(Incident).count() == 2

    # Closed incidents are never reopened automatically.
    fire_alert(client, status="resolved")
    second = db.query(Incident).order_by(Incident.id.desc()).first()
    assert client.post(f"/api/incidents/{second.id}/transition", json={"status": "CLOSED"}, headers=admin_headers).status_code == 200
    assert fire_alert(client)["results"]["created"] == 1
    assert db.query(Incident).count() == 3


def test_lifecycle_transitions_and_validation(client, db, demo_resource, prometheus, operator_headers, admin_headers):
    fire_alert(client)
    incident_id = db.query(Incident).one().id
    url = f"/api/incidents/{incident_id}/transition"

    assert client.post(url, json={"status": "CLOSED"}, headers=admin_headers).status_code == 409  # OPEN -> CLOSED invalid
    ack = client.post(url, json={"status": "ACKNOWLEDGED", "note": "Looking into it"}, headers=operator_headers)
    assert ack.status_code == 200 and ack.json()["status"] == "ACKNOWLEDGED" and ack.json()["acknowledged_at"]
    assert client.post(url, json={"status": "ACKNOWLEDGED"}, headers=operator_headers).status_code == 409
    assert client.post(url, json={"status": "IN_PROGRESS"}, headers=operator_headers).json()["status"] == "IN_PROGRESS"

    # Resolution needs evidence, and is refused while monitoring still reports the alert.
    assert client.post(url, json={"status": "RESOLVED"}, headers=operator_headers).status_code == 422
    prometheus.firing.add("ApplicationUnavailable")
    blocked = client.post(url, json={"status": "RESOLVED", "note": "Should be fine now, I think."}, headers=operator_headers)
    assert blocked.status_code == 409 and "still reports" in blocked.json()["detail"]
    assert db.query(Incident).one().status == "IN_PROGRESS"

    prometheus.firing.clear()
    resolved = client.post(url, json={"status": "RESOLVED", "note": "Health checks pass and the alert cleared."}, headers=operator_headers)
    assert resolved.status_code == 200 and resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["allowed_transitions"] == []  # operator cannot close or reopen

    assert client.post(url, json={"status": "CLOSED"}, headers=operator_headers).status_code == 403
    closed = client.post(url, json={"status": "CLOSED", "note": "Reviewed"}, headers=admin_headers)
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert client.post(url, json={"status": "OPEN", "note": "reopen please now"}, headers=admin_headers).status_code == 409  # terminal

    timeline = [e["event_type"] for e in closed.json()["events"]]
    assert timeline == ["ALERT_RECEIVED", "STATUS_CHANGED", "STATUS_CHANGED", "RESOLVED", "STATUS_CHANGED"]
    actions = audit_actions(db)
    assert actions.count("INCIDENT_STATUS_CHANGED") == 3 and "INCIDENT_STATUS_CHANGE_DENIED" in actions


def test_resolution_is_refused_when_monitoring_cannot_confirm(client, db, demo_resource, prometheus, operator_headers, admin_headers):
    fire_alert(client)
    incident_id = db.query(Incident).one().id
    url = f"/api/incidents/{incident_id}/transition"
    prometheus.available = False
    body = {"status": "RESOLVED", "note": "Prometheus is down, resolving anyway."}
    assert client.post(url, json=body, headers=operator_headers).status_code == 409
    # An operator cannot use the override flag; an administrator can, and it is recorded.
    assert client.post(url, json={**body, "override_monitoring": True}, headers=operator_headers).status_code == 409
    overridden = client.post(url, json={**body, "override_monitoring": True}, headers=admin_headers)
    assert overridden.status_code == 200
    evidence = [e for e in overridden.json()["events"] if e["event_type"] == "RESOLVED"][0]["metadata"]["evidence"]
    assert evidence["monitoring_override"] is True


def test_comments_search_filters_sorting_and_pagination(client, db, demo_resource, operator_headers):
    fire_alert(client, fingerprint="1111111111111111")
    fire_alert(client, alertname="HighApiLatency", fingerprint="2222222222222222", severity="medium")
    fire_alert(client, alertname="HighCpuUsage", fingerprint="3333333333333333", severity="high")
    fire_alert(client, alertname="HighCpuUsage", fingerprint="3333333333333333", status="resolved")

    assert _incidents(client, operator_headers)["total"] == 3
    assert _incidents(client, operator_headers, active_only=True)["total"] == 2
    assert _incidents(client, operator_headers, status="RESOLVED")["total"] == 1
    assert _incidents(client, operator_headers, severity="CRITICAL,MEDIUM")["total"] == 2
    assert _incidents(client, operator_headers, q="latency")["items"][0]["alert_name"] == "HighApiLatency"
    by_severity = _incidents(client, operator_headers, sort="severity", order="asc")["items"]
    assert [i["severity"] for i in by_severity] == ["CRITICAL", "HIGH", "MEDIUM"]
    page = _incidents(client, operator_headers, page=2, page_size=2)
    assert page["page"] == 2 and len(page["items"]) == 1 and page["total"] == 3
    assert client.get("/api/incidents?page_size=1000", headers=operator_headers).status_code == 422

    incident_id = by_severity[0]["id"]
    comment = client.post(f"/api/incidents/{incident_id}/comments", json={"note": "Checked the logs."}, headers=operator_headers)
    assert comment.status_code == 201 and comment.json()["event_type"] == "COMMENT"
    assert client.get("/api/incidents/999999", headers=operator_headers).status_code == 404


def test_stale_signal_is_flagged(client, db, demo_resource, operator_headers):
    fire_alert(client)
    incident = db.query(Incident).one()
    incident.last_occurrence_at = utcnow() - timedelta(minutes=30)
    db.commit()
    assert _incidents(client, operator_headers)["items"][0]["signal_stale"] is True
