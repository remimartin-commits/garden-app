"""Feature schema generation pipeline (draft → audit → finalize)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app import feature_schema as fs
from app.config import Settings


@pytest.fixture
def isolated_settings_env(tmp_path: Path) -> str:
    """Avoid picking up developer ``.env`` keys during pipeline tests."""
    path = tmp_path / "isolated.env"
    path.write_text("", encoding="utf-8")
    return str(path)


def _minimal_schema(name: str) -> dict:
    return {
        "name": name,
        "summary": "s",
        "goals": [],
        "non_goals": [],
        "entities": [],
        "api_endpoints": [],
        "acceptance_criteria": [],
        "implementation_notes": [],
    }


def test_generate_and_store_runs_openai_twice_and_audit_once(
    monkeypatch, tmp_path, isolated_settings_env: str
):
    schema_dir = tmp_path / "feature_schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fs, "feature_schemas_dir", lambda _s: schema_dir)

    draft = _minimal_schema("draft")
    final = _minimal_schema("final")
    openai_mock = MagicMock(side_effect=[draft, final])
    monkeypatch.setattr(fs, "_openai_schema_json_completion", openai_mock)
    audit = {
        "critical_issues": [],
        "improvements": ["add tests"],
        "risk_notes": [],
        "author_instructions_for_revision": "1. Clarify API errors.",
        "overall_verdict": "needs_revision",
    }
    anth_mock = MagicMock(return_value=audit)
    monkeypatch.setattr(fs, "_anthropic_audit_schema", anth_mock)

    out = fs.generate_and_store_feature_schema(
        "Build a small invoicing API",
        Settings(
            _env_file=isolated_settings_env,
            openai_api_key="sk-test-openai",
            anthropic_api_key="sk-test-anthropic",
        ),
    )

    assert out["schema"]["name"] == "final"
    assert openai_mock.call_count == 2
    assert anth_mock.call_count == 1
    anth_mock.assert_called_once()
    kw = anth_mock.call_args.kwargs
    assert kw["topic"] == "Build a small invoicing API"
    assert kw["draft_schema"]["name"] == "draft"

    payload = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert payload["schema_pipeline"]["draft_model"]
    assert payload["schema_pipeline"]["audit_model"]
    assert payload["schema_pipeline"]["finalize_model"]
    assert payload["schema_pipeline"]["draft_schema"]["name"] == "draft"
    assert payload["schema_pipeline"]["audit"]["overall_verdict"] == "needs_revision"


def test_generate_skips_anthropic_when_api_key_missing(
    monkeypatch, tmp_path, isolated_settings_env: str
):
    schema_dir = tmp_path / "feature_schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fs, "feature_schemas_dir", lambda _s: schema_dir)

    draft = _minimal_schema("draft")
    final = _minimal_schema("final")
    openai_mock = MagicMock(side_effect=[draft, final])
    monkeypatch.setattr(fs, "_openai_schema_json_completion", openai_mock)
    anth_mock = MagicMock()
    monkeypatch.setattr(fs, "_anthropic_audit_schema", anth_mock)

    out = fs.generate_and_store_feature_schema(
        "Tiny feature",
        Settings(
            _env_file=isolated_settings_env,
            openai_api_key="sk-test-openai",
            anthropic_api_key="",
        ),
    )

    assert out["schema"]["name"] == "final"
    assert openai_mock.call_count == 2
    anth_mock.assert_not_called()
    payload = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert payload["schema_pipeline"]["audit_model"] == "skipped_no_api_key"
    assert payload["schema_pipeline"]["audit"]["overall_verdict"] == "pass"


def test_generate_requires_anthropic_when_configured(
    monkeypatch, tmp_path, isolated_settings_env: str
):
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        fs.generate_and_store_feature_schema(
            "Tiny feature",
            Settings(
                _env_file=isolated_settings_env,
                openai_api_key="sk-x",
                anthropic_api_key="",
                feature_schema_require_anthropic_audit=True,
            ),
        )
