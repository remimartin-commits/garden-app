from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, status
from pydantic import BaseModel

from app.audit_api import append_audit_log
from app.entities import CustomizationSetting

router = APIRouter(tags=["settings"])

_STORE: dict[tuple[str, str], Any] = {
    ("services", "pricing_tiers"): ["standard", "premium"],
    ("services", "pricing"): "variable",
    ("branding", "logo_url"): "https://example.com/logo.png",
}


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
def get_setting_endpoint(category: str, key: str) -> SettingGetResponse:
    """Return a single customization setting (schema: ``setting`` → ``CustomizationSetting``)."""
    raw = _STORE.get((category, key))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return SettingGetResponse(setting=_to_setting(category, key, raw))


class SettingPatchBody(BaseModel):
    value: Any


@router.patch("/api/v1/settings/{category}/{key}", response_model=SettingGetResponse)
def patch_setting_endpoint(
    category: str,
    key: str,
    body: SettingPatchBody,
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> SettingGetResponse:
    raw = _STORE.get((category, key))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    before = {"category": category, "key": key, "value": raw}
    _STORE[(category, key)] = body.value
    after = {"category": category, "key": key, "value": body.value}
    append_audit_log(
        action="PATCH",
        entity="settings",
        entity_id=0,
        before=before,
        after=after,
        actor_user_id=x_actor_user_id,
    )
    return SettingGetResponse(setting=_to_setting(category, key, body.value))
