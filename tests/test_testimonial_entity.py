import pytest

import app.entities as entities


def test_testimonial_entity_accepts_required_fields():
    testimonial = entities.Testimonial(
        customer_name="Aroha Thompson",
        location="Tauranga, Bay of Plenty",
        quote="The team handled everything from design to handover and kept us informed throughout.",
        project_type="Residential fibreglass pool installation",
        rating=5,
    )

    assert testimonial.customer_name == "Aroha Thompson"
    assert testimonial.location == "Tauranga, Bay of Plenty"
    assert testimonial.project_type == "Residential fibreglass pool installation"
    assert testimonial.rating == 5


def test_testimonial_entity_supports_optional_marketing_fields():
    testimonial = entities.Testimonial(
        customer_name="Michael Lee",
        location="Queenstown, Otago",
        quote="Our resort pool was delivered on schedule with excellent finish quality.",
        project_type="Commercial concrete pool installation",
        rating=5,
        pool_type="Concrete lap pool",
        customer_role="Resort owner",
        image_url="/images/testimonials/queenstown-resort-pool.jpg",
    )

    assert testimonial.pool_type == "Concrete lap pool"
    assert testimonial.customer_role == "Resort owner"
    assert testimonial.image_url == "/images/testimonials/queenstown-resort-pool.jpg"


def test_testimonial_entity_serializes_to_dict():
    testimonial = entities.Testimonial(
        customer_name="Sarah Williams",
        location="Christchurch, Canterbury",
        quote="The installation process was professional from excavation through landscaping.",
        project_type="Family pool installation",
        rating=4,
        pool_type="In-ground family pool",
    )

    assert testimonial.to_dict() == {
        "customer_name": "Sarah Williams",
        "location": "Christchurch, Canterbury",
        "quote": "The installation process was professional from excavation through landscaping.",
        "project_type": "Family pool installation",
        "rating": 4,
        "pool_type": "In-ground family pool",
        "customer_role": None,
        "image_url": None,
    }


@pytest.mark.parametrize(
    "field_name, invalid_value",
    [
        ("customer_name", ""),
        ("location", ""),
        ("quote", ""),
        ("project_type", ""),
    ],
)
def test_testimonial_entity_requires_core_text_fields(field_name, invalid_value):
    values = {
        "customer_name": "Priya Patel",
        "location": "Auckland",
        "quote": "A seamless nationwide installation experience.",
        "project_type": "Residential pool installation",
        "rating": 5,
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=f"{field_name} is required"):
        entities.Testimonial(**values)


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_testimonial_entity_rejects_out_of_range_rating(rating):
    with pytest.raises(ValueError, match="rating must be between 1 and 5"):
        entities.Testimonial(
            customer_name="Emma Brown",
            location="Wellington",
            quote="Great communication and workmanship.",
            project_type="Urban courtyard pool installation",
            rating=rating,
        )


def test_testimonial_entity_requires_integer_rating():
    with pytest.raises(ValueError, match="rating must be an integer"):
        entities.Testimonial(
            customer_name="Noah Wilson",
            location="Nelson",
            quote="Excellent end-to-end service.",
            project_type="Residential plunge pool installation",
            rating="5",
        )
