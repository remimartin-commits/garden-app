from __future__ import annotations
from datetime import datetime, timedelta
from app.entities import AuthSession

def test_auth_session_creation():
    session = AuthSession(
        session_id='test123',
        user_id='user01',
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=1)
    )
    assert session.session_id == 'test123'
    assert session.user_id == 'user01'
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.expires_at, datetime)

if __name__ == "__main__":
    test_auth_session_creation()