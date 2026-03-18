---
Task: t99_implement_user_authentication.md
Worktree: aiwork/t99_implement_user_authentication
Branch: aitask/t99_implement_user_authentication
Base branch: main
---

# Plan: Implement User Authentication — Comprehensive (t99)

## Context

The application currently lacks any authentication mechanism. Users can access
all endpoints without identity verification. This plan implements a complete
authentication system with multiple credential types, session management,
and robust security controls.

The authentication system must support both web-based sessions and API token
access for programmatic clients. Session-based auth was selected over JWT
because the application is server-rendered and sessions simplify CSRF
protection and revocation.

## Architecture Overview

The authentication subsystem sits between the HTTP layer and the application
logic as a cross-cutting concern. It is composed of these components:

- **Identity Store** — manages user records, password hashes, and API tokens
- **Session Manager** — creates, validates, and expires user sessions
- **Auth Middleware** — intercepts requests and enforces access control
- **Audit Logger** — records authentication events for compliance

All components communicate through a shared `AuthContext` object attached to
each request. Downstream handlers inspect `request.auth` to determine the
current user and their permissions.

### Database Schema

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

### Password Hashing

Passwords are hashed using bcrypt with a cost factor of 12. The hash function
is wrapped to allow future migration to argon2id without changing the external
API:

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

### Authentication Flow

```python
def authenticate_user(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email, is_active=True).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None
```

## Component Design

### Identity Store

The identity store wraps the database and provides:

- `create_user(email, password)` — creates user with hashed password
- `get_user(user_id)` — retrieves user by ID
- `find_by_email(email)` — looks up user by email
- `verify_credentials(email, password)` — validates login attempt
- `deactivate_user(user_id)` — soft-deletes a user account

### Session Manager

Sessions stored server-side in Redis with 24-hour TTL:

- Session ID: 32-byte random token, base64url-encoded
- Data: user_id, created_at, last_activity, ip_address
- Sliding window expiry on each request
- Maximum 5 concurrent sessions per user

### Auth Middleware

Request processing pipeline:

1. Extract credentials (session cookie or Bearer token)
2. Validate credentials against identity store
3. Attach `AuthContext` to request
4. Check route-level access requirements
5. Enforce rate limits on auth endpoints

## Implementation Steps

### Step 1: Database Setup

- Add migration `001_add_users_table.py`
- Include index on `email` column
- Add `sessions` table with FK to `users.id`
- Add `api_tokens` table

### Step 2: Core Auth Logic

- Implement `hash_password`, `verify_password`, `authenticate_user`
- Add rate limiting (max 5 attempts per minute per IP)
- Account lockout after 10 consecutive failures

### Step 3: Middleware Integration

- Create `login_required` decorator
- Apply to `/admin/` and `/api/` routes
- Exempt health check and public endpoints
- Add CSRF token validation for POST requests

### Step 4: Routes and Templates

- Login page with form validation
- Logout with session cleanup
- Password reset flow (email-based)
- API token management page

## Risk Assessment

- **Brute force attacks** — mitigated by rate limiting and account lockout
- **Session hijacking** — mitigated by secure cookie flags (HttpOnly, Secure, SameSite=Lax)
- **CSRF** — mitigated by double-submit cookie pattern
- **Password leaks** — mitigated by bcrypt hashing; plaintext never stored or logged
- **Token theft** — API tokens are hashed before storage; original shown only once at creation

## Performance Considerations

- bcrypt hashing adds ~100ms per login attempt (intentional for security)
- Redis session lookups are <1ms per request
- Rate limiting uses a sliding window counter in Redis (O(1) per check)
- User lookups are indexed by email — O(log n) with B-tree index
- Session cleanup runs as a background task every hour

## Verification

- All existing tests pass without modification
- New tests cover: user creation, login success, login failure, logout, session expiry
- Manual testing: login flow works in browser, API tokens work with curl
- Security review: no plaintext passwords stored, sessions expire after 24 hours
- Rate limiting verified: 6th login attempt within 1 minute returns 429
- Performance benchmark: login endpoint handles 100 concurrent requests in <5s
