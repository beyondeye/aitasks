---
name: Security Extended
description: Extended security checks including API security and data protection
reviewtype: security
reviewlabels: [injection, secrets, authentication, input-validation, edge-cases]
similar_to: general/security.md
---

## Review Instructions

### Input Validation
- Check that all user-supplied input is validated before use (form fields, query parameters, headers, file uploads)
- Flag missing boundary checks on numeric inputs (negative values, zero, overflow)
- Look for path traversal vulnerabilities: user-controlled file paths without allowlist checking
- Check that array/list indices from user input are bounds-checked
- Flag deserialization of untrusted data without schema validation (pickle, eval, JSON parsed into executable structures)
- Verify that file upload endpoints validate file type, size, and content (not just extension)
- Check that URL parameters are validated against expected patterns before being used in redirects

### Injection Risks
- Flag string interpolation or concatenation in SQL queries — use parameterized queries instead
- Look for shell command construction from user input — use array-based command execution
- Check for template injection: user input rendered in templates without escaping
- Flag XSS vectors: user-supplied content rendered in HTML without proper escaping or sanitization
- Look for LDAP, XML, or regex injection where user input flows into query/pattern construction

### Secrets and Credentials
- Flag hardcoded API keys, passwords, tokens, or connection strings in source code
- Check that secrets are not logged (logging statements that include auth headers, tokens, or passwords)
- Flag credentials in version-controlled configuration files
- Check that API keys and tokens are loaded from environment variables or secret management systems

### API Security
- Check that rate limiting is applied to authentication endpoints and sensitive operations
- Verify that API responses do not include internal identifiers or debug information in production
- Flag missing CORS configuration or overly permissive CORS policies (Access-Control-Allow-Origin: *)
- Check that pagination endpoints enforce maximum page size to prevent resource exhaustion

### Cryptography
- Flag use of weak hashing algorithms for security purposes (MD5, SHA1 for passwords or signatures)
- Check that passwords are hashed with bcrypt, scrypt, argon2, or PBKDF2 — not plain SHA-256
- Flag hardcoded encryption keys or IVs
- Check that random values for security purposes use cryptographically secure generators
