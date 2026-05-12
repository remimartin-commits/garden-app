from pathlib import Path


STATIC_INDEX = Path("app/static/index.html")


def test_static_site_has_quotes_and_job_workflow() -> None:
    html = STATIC_INDEX.read_text(encoding="utf-8").lower()
    assert "quotes" in html
    assert "new quote" in html or "create quote" in html


def test_sidebar_includes_core_business_pages() -> None:
    html = STATIC_INDEX.read_text(encoding="utf-8").lower()
    assert "dashboard" in html
    assert "customers" in html
    assert "jobs" in html or "schedule" in html
