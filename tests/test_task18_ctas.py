from pathlib import Path


STATIC_INDEX = Path("app/static/index.html")


def test_static_site_has_prominent_quote_and_consultation_ctas():
    html = STATIC_INDEX.read_text(encoding="utf-8").lower()

    assert "request a pool quote" in html or "request a quote" in html
    assert "book a consultation" in html or "consultation" in html
    assert "quote-consult-cta" in html


def test_ctas_reference_home_services_and_project_gallery_contexts():
    html = STATIC_INDEX.read_text(encoding="utf-8").lower()

    assert "service page" in html or "#services" in html or "services" in html
    assert "project gallery" in html or "#gallery" in html or "#projects" in html
