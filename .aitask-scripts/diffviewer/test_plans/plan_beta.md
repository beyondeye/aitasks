---
Task: t99_implement_user_authentication.md
Worktree: aiwork/t99_implement_user_authentication
Branch: aitask/t99_implement_user_authentication
Base branch: main
---

# Plan: Implement User Authentication — File-by-File (t99)

## File: auth/models.py

Create the user model and related database entities.

The authentication system must support both web-based sessions and API token
access for programmatic clients. We chose session-based auth over JWT because
the application is server-rendered and sessions simplify CSRF protection.

```python
from sqlalchemy import Column, String, DateTime, Boolean
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default="now()")
```

Add a `Token` model for API access:

```python
class ApiToken(Base):
    __tablename__ = "api_tokens"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default="now()")
```

## File: auth/handler.py

Implement request handlers for login, logout, and token management.

- Store password hashes using bcrypt with a cost factor of 12
- Implement rate limiting on login attempts (max 5 per minute per IP)
- Add account lockout after 10 consecutive failed attempts

```python
import bcrypt
from app.models import User

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def authenticate_user(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email, is_active=True).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None
```

Add token-based authentication for API clients:

```python
def authenticate_token(token: str) -> User | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    api_token = ApiToken.query.filter_by(token_hash=token_hash).first()
    if api_token and (not api_token.expires_at or api_token.expires_at > datetime.utcnow()):
        return User.query.get(api_token.user_id)
    return None
```

## File: auth/middleware.py

Create ASGI/WSGI middleware for session and token validation.

The application currently has no authentication mechanism. Users can access all
endpoints without any identity verification. This plan adds session-based
authentication with password hashing, login/logout flows, and middleware to
protect sensitive routes.

- Check `Authorization: Bearer <token>` header for API requests
- Check session cookie for browser requests
- Exempt `/health`, `/login`, and `/public/*` routes

## File: tests/test_auth.py

Comprehensive test coverage for the authentication system.

- Test user creation with valid and invalid data
- Test login success and failure paths
- Test session expiry behavior
- Test API token authentication
- Test rate limiting enforcement
- Test CSRF protection on POST endpoints
