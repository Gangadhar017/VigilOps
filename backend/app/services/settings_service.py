"""Runtime-tunable application settings stored in the database.

Only the keys declared in ``SETTING_DEFINITIONS`` can be read or written; each
has a type, bounds and a default.  Changes are restricted to Administrators and
are written to the audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import SystemSetting, User
from app.services.audit_service import record_audit


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    type: str  # "bool" | "int"
    default: Any
    minimum: Optional[int] = None
    maximum: Optional[int] = None


SETTING_DEFINITIONS: Dict[str, SettingDefinition] = {
    d.key: d
    for d in [
        SettingDefinition(
            key="remediation.allow_self_approval",
            label="Allow self-approval of remediation",
            description=(
                "When disabled (recommended), an Administrator cannot approve a remediation "
                "request they submitted themselves; a second person must review it."
            ),
            type="bool",
            default=False,
        ),
        SettingDefinition(
            key="incidents.reopen_window_minutes",
            label="Incident reopen window (minutes)",
            description=(
                "If the same alert fires again within this many minutes after an incident was "
                "resolved, the existing incident is reopened instead of creating a new one. "
                "Closed incidents are never reopened automatically."
            ),
            type="int",
            default=10,
            minimum=0,
            maximum=1440,
        ),
        SettingDefinition(
            key="assistant.enabled",
            label="VigilAI assistant enabled",
            description="Turns the VigilAI chat assistant on or off for all users.",
            type="bool",
            default=True,
        ),
    ]
}


class SettingError(ValueError):
    pass


def _coerce(definition: SettingDefinition, value: Any) -> Any:
    if definition.type == "bool":
        if not isinstance(value, bool):
            raise SettingError(f"{definition.key} must be true or false")
        return value
    if definition.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingError(f"{definition.key} must be a whole number")
        if definition.minimum is not None and value < definition.minimum:
            raise SettingError(f"{definition.key} must be at least {definition.minimum}")
        if definition.maximum is not None and value > definition.maximum:
            raise SettingError(f"{definition.key} must be at most {definition.maximum}")
        return value
    raise SettingError(f"Unsupported setting type for {definition.key}")


def get_setting(db: Session, key: str) -> Any:
    definition = SETTING_DEFINITIONS[key]
    row = db.get(SystemSetting, key)
    if row is None:
        return definition.default
    try:
        return _coerce(definition, row.value)
    except SettingError:
        return definition.default


def list_settings(db: Session) -> List[Dict[str, Any]]:
    rows = {row.key: row for row in db.query(SystemSetting).all()}
    result = []
    for key, definition in SETTING_DEFINITIONS.items():
        row = rows.get(key)
        result.append(
            {
                "key": key,
                "label": definition.label,
                "description": definition.description,
                "type": definition.type,
                "value": get_setting(db, key),
                "default": definition.default,
                "minimum": definition.minimum,
                "maximum": definition.maximum,
                "updated_at": row.updated_at if row else None,
            }
        )
    return result


def update_setting(db: Session, actor: User, key: str, value: Any) -> Dict[str, Any]:
    definition = SETTING_DEFINITIONS.get(key)
    if definition is None:
        raise KeyError(key)
    new_value = _coerce(definition, value)
    previous = get_setting(db, key)

    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=new_value, updated_by=actor.id))
    else:
        row.value = new_value
        row.updated_by = actor.id

    record_audit(
        db,
        action="SETTINGS_UPDATED",
        entity_type="setting",
        entity_id=key,
        actor=actor,
        metadata={"previous": previous, "new": new_value},
    )
    db.commit()
    return next(item for item in list_settings(db) if item["key"] == key)
