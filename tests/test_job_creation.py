from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_job() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        if (os.environ.get("OWNER_PASSWORD") or "").strip():
            login = await ac.post(
                "/login",
                data={
                    "username": os.environ.get("OWNER_USERNAME", "owner"),
                    "password": os.environ["OWNER_PASSWORD"],
                },
            )
            assert login.status_code in (302, 303), login.text
        response = await ac.post(
            "/api/v1/jobs",
            json={
                "service_id": 1,
                "property_id": 1,
                "scheduled_date": "2023-11-01T10:00:00",
                "is_lead": False,
            },
        )
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Job created successfully"}
