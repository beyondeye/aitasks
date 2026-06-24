# applink security model

The security posture of the `ait applink` `wss://` control-plane listener. This
is the current state — when the behaviour changes, edit this page rather than
appending history.

## Trust boundary & threat model

applink is a **LAN-only** listener. A phone pairs by scanning a QR that carries
the routable IP, a single-use pairing token, and the server cert's
SHA-256/base64url fingerprint; the client pins that fingerprint for the pairing
lifetime. The trust boundary is **this machine plus the paired phone on the same
LAN**. Three adversaries are considered:

- **Same-host other user/process** — may try to read runtime state at rest.
- **Malicious or buggy LAN client** — already paired, or attempting to pair, and
  sending hostile frames.
- **Passive network observer** — sees ciphertext only.

Out of scope for Phase 1: a remote relay / broker, end-to-end key exchange
beyond fingerprint pinning, and any non-LAN transport (see `protocol.md`).

## Transport (TLS)

- `wss://` is mandatory — the server refuses to fall back to plaintext.
- The TLS context floors at **TLS 1.2** (1.0/1.1 are disabled) and restricts the
  1.2 cipher list to forward-secret AEAD suites (`ECDHE+AESGCM` / `ECDHE+CHACHA20`).
  The floor is 1.2 rather than 1.3 so the mobile client's TLS stack always
  negotiates; TLS 1.3 suites are AEAD by construction.
- The cert is a self-signed RSA-2048 cert generated once via the system
  `openssl`; its fingerprint is pinned by the client. See `tls.py`.

## Pairing tokens & bearers

- **Pairing tokens:** 256-bit (`secrets.token_urlsafe(32)`), in-memory only
  (never persisted), single-use (consumed on first successful pair), 5-minute
  TTL. Regenerating rotates the unused token without invalidating issued bearers.
- **Bearers:** 256-bit, 7-day TTL, checked (and expired-reaped) on every frame.
  Revocation is immediate (the TUI `r` key, or `bye`) and closes any live socket
  holding the bearer.

## At-rest state

The gitignored runtime dir `aitasks/metadata/applink_sessions/` holds the TLS
key, the cert, `sessions.json` (live bearer secrets), and `applink_audit.log`.
The dir is created **owner-only (`0o700`)** — the structural guard that stops
another local user traversing in — and the TLS key and `sessions.json` are each
written **`0o600`** as defense-in-depth. `sessions.json` is **not** encrypted at
rest: file/dir permissions are the correct layer for the same-host threat, and
encryption would need a key-management story the LAN model does not justify.

## Input validation

The router rejects malformed input before it reaches tmux or the monitor:

- **Pane / window ids** must match the exact tmux id shape (`%N` / `@N`). This
  removes the rich tmux *target-spec* surface (`{mouse}`, `=sess:win.pane`,
  `top`, leading-dash values) for **every** verb that names a pane or window —
  including the workflow verbs whose execution is deferred but which still reach
  tmux while building their confirm/suggest reply.
- **`spawn_tui`** names are constrained to the canonical TUI registry
  (`TUI_NAMES`). `spawn_tui` interpolates the name into a tmux `new-window`
  **shell command**, so an unconstrained name would be arbitrary command
  execution; the allowlist is enforced both at the router and structurally in
  `monitor_core.spawn_tui` (closing the sink for every caller).
- **`send_keys`** passes a `--` end-of-options separator to tmux so a
  leading-dash `keys` value cannot be parsed as a tmux flag.
- Client string fields are length-capped, and a `subscribe` pane-list is capped
  and filtered to valid ids (an over-long list is rejected, not truncated).

## DoS / abuse limits

Enforced in `server.py`:

- **Frame size** — inbound WebSocket frames are capped (`max_size`); the control
  plane only carries small frames.
- **Connection caps** — a global concurrent-connection ceiling and a per-source-IP
  ceiling, so one LAN host cannot starve the legitimate paired phone of the pool.
- **Handshake / idle deadlines** — a TLS/WS opening-handshake timeout (slow-loris
  on the handshake) and a pre-auth idle watchdog that closes a socket which opens
  but never authenticates.
- **Pre-auth frame budget** — an unauthenticated connection may send only a small
  number of frames before it is dropped (malformed-frame flood).

## Audit logging

Security events — auth failures, permission denials, pairing success/failure,
`spawn_tui` rejections, and connection accept/close/limit events — are written to
`applink_audit.log` in the runtime dir (`applink/audit.py`). Secrets are never
logged in full: only a short bearer prefix and the device name appear.

## Residuals & deferred work

Consciously accepted, with the heavier items tracked as follow-up tasks:

- **Time-based per-IP request throttling** — only a *concurrent* per-IP cap
  ships today; sustained-rate token-bucket throttling of authenticated requests
  is a follow-up (`applink_request_rate_limit`).
- **Cert rotation** — the self-signed cert is long-lived with no rotation; a
  shorter validity + client re-pair flow is a follow-up (`applink_cert_rotation`).
- **Bearer rotation** — bearers are static for their 7-day TTL; rotating on each
  resume to shorten a leaked bearer's life is a follow-up
  (`applink_bearer_rotation`).
- **Protocol-version (`v`) enforcement** — accepted leniently to keep the
  additive-compatibility guarantee in `protocol.md` §Versioning.
