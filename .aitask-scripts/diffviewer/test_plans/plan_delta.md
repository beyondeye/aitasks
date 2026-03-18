---
Task: t99_implement_user_authentication.md
Worktree: aiwork/t99_implement_user_authentication
Branch: aitask/t99_implement_user_authentication
Base branch: main
---

# Plan: Implement User Authentication — Minimal (t99)

## Context

The authentication subsystem sits between the HTTP layer and the application
logic as a cross-cutting concern. It consists of three components:

- **Identity Store** — manages user records, password hashes, and API tokens
- **Session Manager** — creates, validates, and expires user sessions
- **Auth Middleware** — intercepts requests and enforces access control

## Implementation

- Create `auth/` package with `store.py`, `sessions.py`, `middleware.py`
- Add Redis dependency for session storage
- Write database migration for users table
- Integrate middleware into the WSGI/ASGI application factory
- Add configuration entries for session TTL, max sessions, rate limits
