from __future__ import annotations

import pytest
from flask import Flask

from app.service_pages import service_templates_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(service_templates_bp)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_create_service_template(client):
    response = client.post(
        "/api/v1/service-templates",
        json={
            "name": "Lawn Mowing",
            "pricing": 30,
            "duration": 60,
            "checklist": ["Check weather", "Assemble equipment"],
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert data["template"]["name"] == "Lawn Mowing"
