import os

import pytest
from fastapi.testclient import TestClient

if not (os.environ.get("OWNER_PASSWORD") or "").strip():
    os.environ["OWNER_PASSWORD"] = "pytest-garden-auth-secret"

from tests.http_helpers import auth_test_client  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return auth_test_client()
