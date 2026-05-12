from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

import pytz
from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load ``.env`` from the repository root (this file lives in ``app/``), not from the
# process current working directory. Otherwise keys in the project ``.env`` are missed when
# uvicorn or tests are launched from another folder.
_REPO_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(_REPO_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # RAG embeddings (OpenAI). Leave empty to run chat-only with no vector retrieval.
    openai_api_key: str = ""
    openai_embed_model: str = "text-embedding-3-small"
    # OpenAI chat model used for non-Ollama generation tasks (feature schemas, etc.).
    openai_chat_model: str = "gpt-5.5"
    # Optional override; if empty, openai_api_key is reused.
    openai_chat_api_key: str = ""
    # If set (e.g. http://localhost:11434/v1), autonomous chat runners use this OpenAI-compatible endpoint (Ollama).
    openai_chat_base_url: str = ""
    # Per-request HTTP timeout (seconds) for OpenAI SDK chat.completions (patch_executor + openai runner).
    # Without this, a hung compatible server can leave autonomy stuck in ``running`` with no further saves.
    openai_chat_request_timeout_seconds: float = Field(default=1200.0, ge=30.0, le=7200.0)
    # --- Feature schema pipeline (/autonomy/start with topic): OpenAI draft+finalize, Anthropic audit ---
    # Empty base URL uses the official OpenAI API (recommended so gpt-5.5 is not sent to Ollama).
    feature_schema_openai_model: str = "gpt-5.5"
    feature_schema_openai_api_key: str = ""
    feature_schema_openai_base_url: str = ""
    feature_schema_audit_anthropic_model: str = "claude-opus-4-7"
    # When True, topic-based schema generation requires ANTHROPIC_API_KEY (Claude audit step).
    # Default False so OPENAI_API_KEY alone is enough to reach the coding loop.
    feature_schema_require_anthropic_audit: bool = False
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ANTHROPIC_API_KEY",
            "CLAUDE_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "FEATURE_SCHEMA_ANTHROPIC_API_KEY",
        ),
    )
    # When OPENAI_CHAT_BASE_URL is set, requests go to that server (Ollama, LM Studio, etc.). Model names must
    # exist there — cloud names like gpt-5.5 are invalid on Ollama. If empty, code falls back from
    # OPENAI_CHAT_MODEL to CHAT_MODEL when the former looks like a cloud-only id.
    autonomous_openai_compatible_model: str = ""
    # Cursor CLI command used by autonomous loop (stdin prompt mode).
    cursor_cli_command: str = ""
    # Target project path where Cursor CLI runs.
    project_root: Path = Path(".")
    # Which vertical the FastAPI app exposes (pool marketing demo).
    codebot_site_vertical: Literal["pool", "all"] = "all"
    # Isolates autonomous runs: use ``pool`` when the agent should focus on ``app/pool`` only.
    autonomous_workspace_domain: Literal["pool", "generic"] = "generic"
    # Autonomous safety defaults.
    autonomous_max_iterations: int = Field(default=10, ge=1, le=100)
    cursor_run_timeout_seconds: int = Field(default=600, ge=30, le=7200)
    # Max wall-clock seconds with no state save while patch_executor (or openai runner) has a task
    # marked running. LLM planning is not bounded by cursor_run_timeout_seconds (that applies to shell
    # commands after the plan). Raise this on slow local models so status-poll stale recovery does not
    # mark tasks needs_review mid-inference.
    patch_executor_stale_step_seconds: int = Field(default=3600, ge=300, le=14400)
    # Runner backend: auto (prefer cursor, fallback openai), cursor, or openai.
    autonomous_runner: Literal["auto", "cursor", "openai", "patch_executor"] = "auto"
    autonomous_fallback_to_openai: bool = True
    autonomous_auto_fix_blocked: bool = True
    autonomous_auto_fix_max_attempts: int = Field(default=3, ge=0, le=20)
    # Force-progress guard: if a task keeps re-validating with no hard failures,
    # advance after N attempts to avoid deadlocks on alignment-only noise.
    autonomous_force_advance_attempts: int = Field(default=4, ge=1, le=20)
    autonomous_parallel_workers: int = Field(default=4, ge=1, le=12)
    # Run full-suite verification every N step attempts (focused checks run otherwise).
    autonomous_full_verification_every: int = Field(default=5, ge=1, le=50)
    # Comma-separated protected paths that patch_executor must never edit.
    autonomous_protected_paths: str = (
        "app/main.py,app/autonomy_api.py,app/autonomous_loop.py,"
        "app/quote_enquiries.py,app/patch_executor.py,app/entities.py"
    )
    # Comma-separated paths where patch_executor must not use write_file (full replace).
    # Enforced for isolated runs too (replace_in_file / append_file still allowed).
    autonomous_write_file_denylist: str = (
        "app/entities.py,app/main.py,app/config.py,app/autonomous_loop.py,"
        "app/autonomy_api.py,app/patch_executor.py,app/quote_enquiries.py"
    )
    # Escalation writer (Personality AI handoff to manual / default agent).
    escalation_profile: str = "default"
    # Comma-separated: file, clipboard, webhook (stub), desktop_notification (stub).
    escalation_dispatch_modes: str = "file"
    # Queue handoff for Cursor IDE: project hook `.cursor/hooks/escalation_stop_followup.py` emits
    # followup_message on the Composer ``stop`` event (auto-submitted user message).
    escalation_cursor_inject_enabled: bool = True
    escalation_cursor_inject_max_chars: int = Field(default=12000, ge=2000, le=100000)
    # Run-isolation defaults: each autonomous run executes in a dedicated folder.
    autonomous_isolate_runs: bool = True
    autonomous_runs_dir: Path = Path("./outputs")
    autonomous_cleanup_runs_on_start: bool = True
    autonomous_run_retention: int = Field(default=5, ge=1, le=100)
    # Primary coding model (Vibe studio /generate /refine): e.g. codellama:7b
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    chat_model: str = "codellama:7b"
    # RAG /chat answer model (optional). If empty, chat_model is used for both.
    rag_chat_model: str = ""
    chroma_persist_dir: Path = Path("./.chroma")
    docs_dir: Path = Path("./data/docs")
    # Local-only profile storage (style defaults, sync queue).
    user_data_dir: Path = Path("./data/user")
    # Lightweight HEAD/GET probe to detect outbound connectivity.
    sync_probe_url: str = "https://huggingface.co"
    sync_probe_timeout_seconds: float = 3.0
    # Optional HTTPS endpoint for queued backups when offline-first sync is enabled.
    sync_backup_url: str = ""
    sync_backup_token: str = ""
    rag_top_k: int = 6
    # Retrieve more chunks then trim (dedupe overlap); improves recall vs pure top_k.
    rag_fetch_multiplier: int = Field(default=2, ge=1)
    # Cap injected context size so long retrievals do not dominate the prompt.
    rag_max_context_chars: int = Field(default=12000, ge=2000)
    chunk_tokens: int = 450
    chunk_overlap_tokens: int = 80
    # "markdown" splits on headings then token-chunks each section (better for .md docs).
    rag_chunk_strategy: Literal["tokens", "markdown"] = "tokens"
    # Set True to wipe the vector store and re-embed all files (e.g. after editing data/docs)
    force_reingest: bool = False


def get_settings() -> Settings:
    return Settings()


def rag_answer_model(settings: Settings) -> str:
    """Ollama model name for POST /chat (RAG). Falls back to coding chat_model."""
    r = (settings.rag_chat_model or "").strip()
    return r if r else settings.chat_model


def vertical_autonomy_blocklist(settings: Settings) -> list[str]:
    """Paths under PROJECT_ROOT that must not be touched by patch agents for this vertical."""
    return []


def effective_autonomous_protected_paths(settings: Settings, project_root: Path) -> list[str]:
    """Paths the patch executor must not edit.

    When ``project_root`` matches ``settings.project_root``, we enforce the configured
    comma-separated blocklist so autonomous runs cannot alter Codebot's own routing/API.

    When the resolved roots differ (typical isolated run under ``outputs/...``), the host
    blocklist is not applied; optional vertical exclusions from
    ``vertical_autonomy_blocklist`` still apply when non-empty.

    Vertical rules come from ``Settings.autonomous_workspace_domain``.
    """
    raw = [
        p.strip()
        for p in str(settings.autonomous_protected_paths or "").split(",")
        if p.strip()
    ]
    vertical = vertical_autonomy_blocklist(settings)
    try:
        host = settings.project_root.resolve()
        run = Path(project_root).resolve()
    except OSError:
        return list(dict.fromkeys(raw + vertical))
    if run == host:
        base = raw
    else:
        base = []
    merged = list(dict.fromkeys(base + vertical))
    return merged


def effective_autonomous_write_file_denylist(settings: Settings) -> list[str]:
    """Paths where ``write_file`` is forbidden (any project root, including isolated runs).

    Stops small models from replacing entire infrastructure modules while still allowing
    ``replace_in_file`` / ``append_file`` for the same paths.
    """
    return list(
        dict.fromkeys(
            p.strip()
            for p in str(settings.autonomous_write_file_denylist or "").split(",")
            if p.strip()
        )
    )


def get_utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def convert_to_local_time(utc_time_str: str, timezone: str = "Pacific/Auckland") -> str:
    utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
    local_tz = pytz.timezone(timezone)
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt.strftime("%Y-%m-%dT%H:%M:%S%z")


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "owner")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in (
    "1",
    "true",
    "yes",
)


def auth_gate_enabled() -> bool:
    """When false (empty owner password), login middleware is skipped for local dev."""
    return bool((OWNER_PASSWORD or "").strip())


S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "").strip()
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "").strip()
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "").strip()
S3_REGION = (os.environ.get("S3_REGION") or "eu-central-1").strip()
S3_JOBS_PREFIX = (os.environ.get("S3_JOBS_PREFIX") or "job-attachments").strip().strip("/") or "job-attachments"
S3_PUBLIC_BASE_URL = os.environ.get("S3_PUBLIC_BASE_URL", "").strip().rstrip("/")


def s3_job_attachments_configured() -> bool:
    """True when Hetzner Object Storage (S3 API) env vars are present for photo uploads."""
    return bool(
        S3_ENDPOINT_URL
        and S3_ACCESS_KEY_ID
        and S3_SECRET_ACCESS_KEY
        and S3_BUCKET_NAME
        and S3_PUBLIC_BASE_URL
    )