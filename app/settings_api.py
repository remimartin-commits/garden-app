from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit_api import append_audit_log
from app.database import get_db
from app.entities import CustomizationSetting
from app.models import AppSetting

router = APIRouter(tags=["settings"])

_DEFAULT_SETTINGS: dict[tuple[str, str], Any] = {
    ("services", "pricing_tiers"): ["standard", "premium"],
    ("services", "pricing"): "variable",
    ("branding", "logo_url"): "https://example.com/logo.png",
    ("business", "name"): "",
    ("business", "phone"): "",
    ("business", "email"): "",
    ("business", "region"): "",
}


def ensure_default_settings(db: Session) -> None:
    """Insert default rows for known keys when missing (idempotent)."""
    for (category, key), val in _DEFAULT_SETTINGS.items():
        existing = db.query(AppSetting).filter_by(category=category, key=key).first()
        if existing is None:
            db.add(
                AppSetting(
                    category=category,
                    key=key,
                    value=_encode_value(val),
                )
            )
    db.commit()


def _encode_value(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _decode_value(raw: str | None) -> Any:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return raw


class SettingGetResponse(BaseModel):
    setting: CustomizationSetting


def _to_setting(category: str, key: str, value: Any) -> CustomizationSetting:
    if isinstance(value, (dict, list)):
        current = json.dumps(value)
    else:
        current = str(value)
    return CustomizationSetting(
        name=f"{category}/{key}",
        description=f"Customization setting for {category}/{key}.",
        default_value="",
        current_value=current,
        owner_controlled=True,
    )


_SCHEMAS: dict[str, dict] = {
    "jobs": {"type": "object", "properties": {"name": {"type": "string"}}},
}


@router.get("/api/v1/settings/schemas/{category}")
def get_settings_schema(category: str) -> dict[str, Any]:
    body = _SCHEMAS.get(category)
    if body is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    return {"schema": body}


@router.get("/api/v1/settings/{category}/{key}", response_model=SettingGetResponse)
def get_setting_endpoint(category: str, key: str, db: Session = Depends(get_db)) -> SettingGetResponse:
    """Return a single customization setting (schema: ``setting`` → ``CustomizationSetting``)."""
    row = db.query(AppSetting).filter_by(category=category, key=key).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    raw = _decode_value(row.value)
    return SettingGetResponse(setting=_to_setting(category, key, raw))


class SettingPatchBody(BaseModel):
    value: Any


@router.patch("/api/v1/settings/{category}/{key}", response_model=SettingGetResponse)
def patch_setting_endpoint(
    category: str,
    key: str,
    body: SettingPatchBody,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> SettingGetResponse:
    row = db.query(AppSetting).filter_by(category=category, key=key).first()
    before_raw: Any = None
    if row is None:
        row = AppSetting(category=category, key=key, value=None)
        db.add(row)
        db.flush()
    else:
        before_raw = _decode_value(row.value)

    row.value = _encode_value(body.value)
    after_raw = _decode_value(row.value)
    db.commit()
    db.refresh(row)

    append_audit_log(
        action="PATCH",
        entity="settings",
        entity_id=0,
        before={"category": category, "key": key, "value": before_raw},
        after={"category": category, "key": key, "value": after_raw},
        actor_user_id=x_actor_user_id,
    )
    return SettingGetResponse(setting=_to_setting(category, key, after_raw))
