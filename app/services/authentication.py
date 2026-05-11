
from app.entities import User

def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.verify_password(password):
        return user, 'fake-session-token'
    return None, None
