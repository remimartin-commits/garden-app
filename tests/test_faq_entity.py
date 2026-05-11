import pytest

from app.entities import FAQ, FAQ_REQUIRED_FIELDS


def test_faq_required_fields_and_serialisation():
    faq = FAQ(
        faq_id="installation-timeline",
        question="How long does a complete swimming pool installation take?",
        answer="Most residential pool installations are planned around consultation, design, excavation, construction, finishing, and handover milestones.",
        category="Installation Process",
        audience="Homeowners",
        display_order=1,
        related_services=["Design consultation", "Excavation", "Pool construction"],
        applies_to_regions=["North Island", "South Island"],
        is_featured=True,
    )

    assert FAQ_REQUIRED_FIELDS == (
        "faq_id",
        "question",
        "answer",
        "category",
        "audience",
        "display_order",
    )
    assert faq.to_dict() == {
        "faq_id": "installation-timeline",
        "question": "How long does a complete swimming pool installation take?",
        "answer": "Most residential pool installations are planned around consultation, design, excavation, construction, finishing, and handover milestones.",
        "category": "Installation Process",
        "audience": "Homeowners",
        "display_order": 1,
        "related_services": ["Design consultation", "Excavation", "Pool construction"],
        "applies_to_regions": ["North Island", "South Island"],
        "is_featured": True,
    }


def test_faq_rejects_missing_required_text_fields():
    with pytest.raises(ValueError, match="question is required"):
        FAQ(
            faq_id="coverage",
            question=" ",
            answer="We provide pool installation services throughout New Zealand.",
            category="Coverage",
            audience="All customers",
            display_order=2,
        )


def test_faq_rejects_invalid_display_order():
    with pytest.raises(ValueError, match="display_order must be a positive integer"):
        FAQ(
            faq_id="quotes",
            question="Can I request a quote online?",
            answer="Yes, customers can send location, site details, preferred pool type, and timing requirements through the quote enquiry workflow.",
            category="Quotes",
            audience="Homeowners",
            display_order=0,
        )


def test_faq_requires_new_zealand_coverage_scope():
    with pytest.raises(ValueError, match="applies_to_regions must include at least one New Zealand coverage area"):
        FAQ(
            faq_id="empty-coverage",
            question="Do you work nationwide?",
            answer="Yes, the installation team coordinates projects across New Zealand.",
            category="Coverage",
            audience="All customers",
            display_order=3,
            applies_to_regions=[],
        )
