"""Persist vibe style profile locally (privacy-preserving default)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings
from app.vibe import VibeStyleProfile

logger = logging.getLogger(__name__)


def style_profile_path(settings: Settings) -> Path:
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.user_data_dir / "style_profile.json"


def load_saved_style(settings: Settings) -> VibeStyleProfile | None:
    path = style_profile_path(settings)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return VibeStyleProfile.model_validate(raw)


def save_style(settings: Settings, profile: VibeStyleProfile) -> None:
    path = style_profile_path(settings)
    path.write_text(
        json.dumps(profile.model_dump(), indent=2),
        encoding="utf-8",
    )


def save_style_with_optional_backup(
    settings: Settings,
    profile: VibeStyleProfile,
) -> dict[str, bool]:
    """Write style_profile.json and mirror FastAPI backup / queue logic."""
    save_style(settings, profile)
    backup_url = (settings.sync_backup_url or "").strip()
    if not backup_url:
        return {"saved": True, "queued": False}

    from app.connectivity import probe_online
    from app import sync_queue

    db_path = settings.user_data_dir / "sync_queue.sqlite3"
    payload = profile.model_dump()
    online = probe_online(
        settings.sync_probe_url,
        timeout_seconds=settings.sync_probe_timeout_seconds,
    )
    queued = False
    if online:
        try:
            sync_queue.push_backup(
                backup_url,
                settings.sync_backup_token,
                "style_profile",
                payload,
            )
        except Exception as e:
            logger.warning("Immediate style backup failed; queueing: %s", e)
            sync_queue.enqueue_job(db_path, "style_profile", payload)
            queued = True
    else:
        sync_queue.enqueue_job(db_path, "style_profile", payload)
        queued = True
    return {"saved": True, "queued": queued}
