---
Task: t99_implement_user_authentication.md
Worktree: aiwork/t99_implement_user_authentication
Branch: aitask/t99_implement_user_authentication
Base branch: main
---

# Plan: Implement User Authentication (t99)

## Context

The application currently has no authentication mechanism. Users can access all
endpoints without any identity verification. This plan adds session-based
authentication with password hashing, login/logout flows, and middleware to
protect sensitive routes.

The authentication system must support both web-based sessions and API token
access for programmatic clients. We chose session-based auth over JWT because
the application is server-rendered and sessions simplify CSRF protection.

## Step 1: Setup Database Schema

Create the users table and session storage.

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

- Add migration file `migrations/versions/001_add_users_table.py`
- Include index on `email` column for fast lookups
- Add `sessions` table with foreign key to `users.id`

## Step 2: Implement Authentication Logic

Build the core authentication functions.

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

- Store password hashes using bcrypt with a cost factor of 12
- Implement rate limiting on login attempts (max 5 per minute per IP)
- Add account lockout after 10 consecutive failed attempts

## Step 3: Add Authentication Middleware

Create middleware that checks for valid sessions on protected routes.

```python
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated
```

- Apply middleware to all routes under `/admin/` and `/api/`
- Exempt health check and public endpoints
- Add CSRF token validation for all POST requests

## Step 4: Create Login/Logout Routes

```python
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = authenticate_user(
            request.form["email"],
            request.form["password"]
        )
        if user:
            session["user_id"] = user.id
            return redirect(url_for("dashboard.index"))
        flash("Invalid credentials", "error")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
```

## Verification

- All existing tests pass without modification
- New tests cover: user creation, login success, login failure, logout, session expiry
- Manual testing: login flow works in browser, API tokens work with curl
- Security review: no plaintext passwords stored, sessions expire after 24 hours
- Rate limiting verified: 6th login attempt within 1 minute returns 429
