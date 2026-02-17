---
name: Security
description: Check for injection risks, secrets exposure, and OWASP top 10 patterns
---

## Review Instructions

### Input Validation
- Check that all user-supplied input is validated before use (form fields, query parameters, headers, file uploads)
- Flag missing boundary checks on numeric inputs (negative values, zero, overflow)
- Look for path traversal vulnerabilities: user-controlled file paths used without canonicalization or allowlist checking (e.g., `../../../etc/passwd`)
- Check that array/list indices from user input are bounds-checked
- Flag deserialization of untrusted data without schema validation (pickle, eval, JSON parsed into executable structures)

### Injection Risks
- Flag string interpolation or concatenation in SQL queries — use parameterized queries instead
- Look for shell command construction from user input (`os.system()`, `subprocess` with `shell=True`, backticks) — use array-based command execution
- Check for template injection: user input rendered in templates without escaping
- Flag XSS vectors: user-supplied content rendered in HTML without proper escaping or sanitization
- Look for LDAP, XML, or regex injection where user input flows into query/pattern construction
- Check for header injection in HTTP responses (user input in Set-Cookie, Location, or other headers)

### Secrets and Credentials
- Flag hardcoded API keys, passwords, tokens, or connection strings in source code
- Check that secrets are not logged (look for logging statements that include auth headers, tokens, or passwords)
- Flag credentials in version-controlled configuration files (even if the repo is private)
- Check that API keys and tokens are loaded from environment variables or secret management systems
- Look for secrets in error messages or stack traces that could be exposed to users

### Authentication and Authorization
- Check that all API endpoints and routes have appropriate authentication checks
- Flag missing authorization checks — authenticated users should only access resources they own or are permitted to see
- Look for privilege escalation paths: endpoints that accept a user ID parameter without verifying the caller has permission
- Check that password comparison uses constant-time comparison to prevent timing attacks
- Flag insecure session management: sessions that don't expire, tokens stored in localStorage, missing CSRF protection

### Cryptography
- Flag use of weak hashing algorithms for security purposes (MD5, SHA1 for passwords or signatures)
- Check that passwords are hashed with bcrypt, scrypt, argon2, or PBKDF2 — not plain SHA-256
- Flag hardcoded encryption keys or IVs
- Check that random values for security purposes use cryptographically secure generators (not `math.random()` or `rand()`)
- Flag disabled TLS certificate verification (`verify=False`, `InsecureSkipVerify`)
