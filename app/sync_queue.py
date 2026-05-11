"""SQLite-backed queue for actions to retry when back online."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at REAL NOT NULL,
            synced_at REAL
        )
        """
    )
    conn.commit()
    return conn


def enqueue_job(db_path: Path, kind: str, payload: dict[str, Any]) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO sync_jobs (kind, payload, created_at) VALUES (?, ?, ?)",
            (kind, json.dumps(payload), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def pending_count(db_path: Path) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_jobs WHERE synced_at IS NULL"
        ).fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()


def flush_pending(
    db_path: Path,
    *,
    online: bool,
    backup_url: str,
    backup_token: str,
) -> int:
    """POST pending payloads to backup_url when online. Returns number flushed."""
    if not online or not (backup_url or "").strip():
        return 0

    conn = _connect(db_path)
    flushed = 0
    try:
        rows = conn.execute(
            "SELECT id, kind, payload FROM sync_jobs WHERE synced_at IS NULL ORDER BY id"
        ).fetchall()
        for row in rows:
            job_id = row["id"]
            payload = json.loads(row["payload"])
            try:
                push_backup(backup_url.strip(), backup_token, row["kind"], payload)
                conn.execute(
                    "UPDATE sync_jobs SET synced_at = ? WHERE id = ?",
                    (time.time(), job_id),
                )
                flushed += 1
            except Exception as e:
                logger.warning("Sync job %s failed: %s", job_id, e)
                break
        conn.commit()
    finally:
        conn.close()
    return flushed


def push_backup(url: str, token: str, kind: str, payload: dict[str, Any]) -> None:
    import urllib.request

    body = json.dumps({"kind": kind, "payload": payload}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status and not (200 <= resp.status < 300):
            raise RuntimeError(f"backup HTTP {resp.status}")


def run_flush_if_configured(
    db_path: Path,
    *,
    probe: Callable[[], bool],
    backup_url: str,
    backup_token: str,
) -> int:
    online = probe()
    return flush_pending(
        db_path, online=online, backup_url=backup_url, backup_token=backup_token
    )
