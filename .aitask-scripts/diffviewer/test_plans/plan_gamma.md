---
Task: t99_implement_user_authentication.md
Worktree: aiwork/t99_implement_user_authentication
Branch: aitask/t99_implement_user_authentication
Base branch: main
---

# Plan: Implement User Authentication — Architecture First (t99)

## Architecture Overview

The authentication subsystem sits between the HTTP layer and the application
logic as a cross-cutting concern. It consists of three components:

- **Identity Store** — manages user records, password hashes, and API tokens
- **Session Manager** — creates, validates, and expires user sessions
- **Auth Middleware** — intercepts requests and enforces access control

All components communicate through a shared `AuthContext` object that is
attached to each request. Downstream handlers can inspect `request.auth` to
determine the current user and their permissions.

The system follows the principle of defense in depth: even if middleware is
bypassed, individual route handlers can independently verify authentication
status through the `AuthContext`.

## Component Design

### Identity Store

The identity store wraps the database layer and provides a clean API for
user management:

- `create_user(email, password)` — creates user with hashed password
- `get_user(user_id)` — retrieves user by ID
- `find_by_email(email)` — looks up user by email address
- `verify_credentials(email, password)` — validates login attempt
- `deactivate_user(user_id)` — soft-deletes a user account

Password hashing uses argon2id with the following parameters:
- Memory: 64 MiB
- Iterations: 3
- Parallelism: 4

### Session Manager

Sessions are stored server-side in Redis with a 24-hour TTL:

- Session ID is a 32-byte random token, base64url-encoded
- Session data includes: user_id, created_at, last_activity, ip_address
- Sessions are refreshed on each request (sliding window expiry)
- Maximum 5 concurrent sessions per user

### Auth Middleware

The middleware pipeline processes requests in this order:

1. Extract credentials (session cookie or Bearer token)
2. Validate credentials against the identity store
3. Attach `AuthContext` to request
4. Check route-level access requirements
5. Enforce rate limits on authentication endpoints

## Implementation

- Create `auth/` package with `store.py`, `sessions.py`, `middleware.py`
- Add Redis dependency for session storage
- Write database migration for users table
- Integrate middleware into the WSGI/ASGI application factory
- Add configuration entries for session TTL, max sessions, rate limits

## Verification

- All existing tests pass without modification
- New tests cover: user creation, login success, login failure, logout, session expiry
- Manual testing: login flow works in browser, API tokens work with curl
- Security review: no plaintext passwords stored, sessions expire after 24 hours
- Rate limiting verified: 6th login attempt within 1 minute returns 429
