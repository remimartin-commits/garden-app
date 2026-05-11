"""Settings: Anthropic API key env aliases and repo-root .env path."""

from pathlib import Path

import pytest

from app.config import Settings


def test_anthropic_api_key_reads_claude_api_key_alias(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("# no API keys here\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FEATURE_SCHEMA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test-from-claude-alias")
    s = Settings(_env_file=str(empty_env))
    assert s.anthropic_api_key == "sk-ant-test-from-claude-alias"


def test_env_file_is_repo_root_dotenv() -> None:
    import app.config as cfg

    env_path = Path(str(Settings.model_config["env_file"]))
    assert env_path.name == ".env"
    assert env_path.parent == cfg._REPO_ROOT


def test_status_payload_includes_env_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
    from app.autonomous_loop import status_payload
    from app.config import get_settings

    st = status_payload(get_settings())
    assert st.get("env_anthropic_configured") is True
    assert st.get("env_openai_for_schema_configured") is True
