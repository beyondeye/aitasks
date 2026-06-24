---
Task: t985_applink_security_review_hardening.md
Worktree: (none — profile 'fast' works on current branch)
Branch: main
Base branch: main
---

# t985 — applink security review & hardening

## Context

The `ait applink` `wss://` WebSocket control-plane listener landed in t822_7
without a dedicated security review (a fresh network listener is new attack
surface). `tls.py:10-11` and `protocol.md:206-209` both name *this* task as the
deferred "follow-up security task".

This task performs the review and implements a **core hardening set** (scoped
with the user): low-risk, applink-local fixes with **no UX change**, plus two
deliberately-shared `monitor_core` fixes that close command/argument-injection
sinks at their source. Heavyweight lifecycle items (automatic cert rotation,
bearer rotation) and time-based per-IP request throttling are **deferred to
follow-up tasks** created at Step 8d. Bearer TTL stays 7 days. Encryption-at-rest
of `sessions.json` is **rejected** in favour of directory + file permissions —
the right layer for the local-multi-user threat, with no key-management story to
invent.

> **Revised after review:** a first pass missed the highest-severity issue —
> `spawn_tui` is a shell-command-execution sink, not just an argv issue — and
> under-applied the pane-id validator and the DoS limits. This plan addresses all
> four review findings. See "Threat model" #1, #4, #5, #6.

Deliverables (from the task): a short threat-model note, the hardening changes,
and tests.

## Threat model (the note → `aidocs/applink/security.md`)

Scope: a LAN-only `wss://` listener; self-signed cert pinned by fingerprint in
the QR; single-use pairing tokens exchanged for 7-day bearers; verb gating by
permission profile. Trust boundary = local machine + the paired phone on the
LAN. Adversaries: (a) another user/process on the **same host** reading state at
rest; (b) a malicious/buggy **paired or pairing** client on the LAN; (c) a
passive network observer.

Findings (all source-verified), ordered by severity:

| # | Area | Finding (file:line) | Severity |
|---|------|---------------------|----------|
| 1 | **RCE** | `spawn_tui` builds `f"ait {tui_name}"` as the tmux `new-window` **shell command**; `tui_name` is only type-checked, so a `full`-profile client gets arbitrary command execution (`monitor_core.py:1423-1428`, `router.py:294-298`) | **Critical** |
| 2 | At-rest | `sessions.json` (live bearers) written with default umask — no perms, unlike the key's `chmod 0o600` (`sessions.py:199-209`) | High |
| 3 | At-rest | runtime dir not locked down; key `chmod` best-effort with a small post-write window (`tls.py:66-70`) | Medium |
| 4 | Input | pane/window verbs accept any `pane_id`/`window_id` string — no tmux-id format check, so the rich tmux *target-spec* surface (`{mouse}`, `=sess:win.pane`) is reachable; applies to send_enter/send_keys/forward_key/focus/cycle_compare_mode/request_keyframe/kill_pane/restart_task/pick_next_sibling and `window_id` in kill_window; even "deferred" verbs reach tmux via `capture_pane`/`_resolve_pane_task` (`router.py:224-316,378-485`) | High |
| 5 | Input | `send_keys` passes `keys` to tmux with no `--`, so a leading-dash value (`-R`, `-N`) is parsed as a tmux **flag** (`monitor_core.py:1284-1288`) | High |
| 6 | DoS | no connection cap; no `max_size`; no pre-auth frame budget; no pre-auth idle/handshake deadline (an idle unauthenticated socket holds a slot); no per-IP cap (one host can exhaust all slots) (`server.py:62,102-104,127-149`) | High |
| 7 | DoS | unbounded `subscribe` pane-list grows `Subscription.panes` + the push loop (`router.py:261-277`) | Medium |
| 8 | Audit | zero logging of `AUTH_FAILED` / `PERMISSION_DENIED` / pairing events (no logger in the package) | Medium |

Residuals consciously left (documented in the note + tracked as follow-ups where
noted): **time-based per-IP request throttling** (concurrent per-IP cap is
implemented; token-bucket rate-limiting → follow-up `applink_request_rate_limit`),
7-day bearer TTL (user choice), no protocol-version (`v`) enforcement (keep
additive-compat per `protocol.md` §Versioning), 10-year cert + static bearer (→
deferred follow-ups).

---

## Implementation

Profile 'fast' → current branch. Changes grouped below; commit logically (Step 8).

### 1. Close the `spawn_tui` RCE (finding 1) — structural, at the source

**`monitor_core.py:1423`** `spawn_tui` — `TUI_NAMES` is **already imported**
(`monitor_core.py:40`). Refuse any non-registry name before it reaches the shell:
```python
def spawn_tui(self, tui_name: str) -> bool:
    if tui_name not in TUI_NAMES:          # canonical allowlist (lib/tui_registry)
        return False
    rc, _ = self.tmux_run([
        "new-window", "-t", tmux_window_target(self.session, ""),
        "-n", tui_name, f"ait {tui_name}",
    ])
    return rc == 0
```
This closes the command-execution sink for **every** caller (desktop monitor,
applink), matching the user's prefer-structural-fix and shared-`monitor_core`
decisions. Blast radius: desktop spawn paths already pass registry names
(`get_missing_tuis()` derives from `tui_names`), so valid launches are unaffected.

**`router.py:294-298`** — defense-in-depth + audit: reject `tui_name not in
TUI_NAMES` with `ERR_BAD_PAYLOAD` and emit an audit warning, so the attempt is
logged and never reaches the monitor. (Import `TUI_NAMES`; the applink modules put
`.aitask-scripts` on `sys.path`, so `from tui_registry import TUI_NAMES` resolves.)

### 2. One pane-id/window-id validator, applied everywhere (findings 4, 7)

**`router.py`** — add near `_req_str` (`router.py:539`):
```python
import re
_PANE_ID_RE = re.compile(r"^%\d+$")
_WINDOW_ID_RE = re.compile(r"^@\d+$")
_MAX_STR = 4096
_MAX_PANES = 256

def _req_pane_id(self, payload, key="pane_id"):
    v = self._req_str(payload, key)
    return v if v is not None and _PANE_ID_RE.match(v) else None

def _req_window_id(self, payload, key="window_id"):
    v = self._req_str(payload, key)
    return v if v is not None and _WINDOW_ID_RE.match(v) else None
```
Apply consistently — **every** handler that names a pane/window routes through
the validator, including the deferred verbs (they still hit tmux in their
build/suggest phase):
- `pane_id` via `_req_pane_id`: `send_enter` (226), `send_keys` (232),
  `forward_key` (241), `focus` (249), `request_keyframe` (280),
  `cycle_compare_mode` (288), `_kill_pane` (379), `_restart_task` (411),
  `_pick_next_sibling` (455).
- `window_id` via `_req_window_id`: `_kill_window` (395).
- `subscribe` (261-277): enforce the **same `^%\d+$` rule per entry** (not just
  str-filter + cap): `panes = [p for p in panes if isinstance(p, str) and _PANE_ID_RE.match(p)]`,
  then if the *original* list exceeded `_MAX_PANES` → `_bad_field` (no silent
  truncation). This makes the pane-id contract uniform across single-pane verbs
  and the subscription list.
- Envelope/string caps in `handle` (142-154): reject `len(verb) > _MAX_STR` or
  `len(msg_id) > _MAX_STR`; in `send_keys`, reject `len(keys) > _MAX_STR`.

All rejections use the existing `_bad_field(...)` → `ERR_BAD_PAYLOAD`.

### 3. tmux `--` separator in the shared monitor (finding 5)

**`monitor_core.py:1278-1289`** `send_keys` — insert `--` before `keys`:
```python
cmd = ["send-keys", "-t", pane_id]
if literal:
    cmd.append("-l")
cmd.append("--")
cmd.append(keys)
```
Add `--` to `send_enter` (1275) for consistency. `forward_key` inherits it.
Verified safe (shared with desktop preview-zone forwarding): normal key
names/literal text are positional args either way; `--` only changes a leading-`-`
value, which previously injected a flag and now is a rejected key name. tmux 3.6b's
parser supports `--`.

### 4. Runtime-dir + file permissions (findings 2, 3) — structural

**`paths.py`** — shared helper:
```python
def ensure_secure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)        # owner-only: structural guard even under a lax umask
    except OSError:
        pass
    return path
```
- `tls.py:42` `ensure_cert` → use `paths.ensure_secure_dir(cert_dir)`; keep key `chmod 0o600`.
- `sessions.py:202` `_save` → `ensure_secure_dir(self._dir)`, and lock the temp
  file before the atomic rename so the live `sessions.json` is always `0o600`:
  ```python
  tmp.write_text(json.dumps(payload, indent=2))
  try:
      tmp.chmod(0o600)
  except OSError:
      pass
  tmp.replace(self._path())
  ```

### 5. TLS suite/version pinning (the original "crypto review", finding alongside)

**`tls.py:85-89`** `build_ssl_context`:
```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2          # drop TLS 1.0/1.1
ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!eNULL:!MD5")
ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
```
Floor at **1.2, not 1.3** (mobile-client TLS-stack compat); AEAD-only suites for 1.2.

### 6. DoS limits at the server (finding 6)

**`server.py`** — constants + enforcement:
```python
MAX_CONNECTIONS = 64        # global concurrent-socket ceiling
MAX_PER_IP = 8              # per-source-IP concurrent ceiling
MAX_FRAME_BYTES = 64 * 1024 # control-plane frames are tiny
MAX_PREAUTH_FRAMES = 16     # frames allowed before a successful pair/resume
PREAUTH_TIMEOUT = 15.0      # seconds an unauthenticated socket may live
OPEN_TIMEOUT = 10.0         # TLS/WS opening-handshake deadline (slow-loris)
```
- `start` (102-104): `websockets.serve(..., max_size=MAX_FRAME_BYTES, open_timeout=OPEN_TIMEOUT)` (keepalive ping defaults still cull dead peers).
- `_handle` (127): derive `ip = ws.remote_address[0] if ws.remote_address else "?"`. Before registering the conn:
  - global cap: `if len(self._conns) >= MAX_CONNECTIONS: <audit>; await ws.close(); return`
  - per-IP cap: track `self._conns_by_ip: dict[str,int]`; `if self._conns_by_ip.get(ip,0) >= MAX_PER_IP: <audit>; await ws.close(); return`; else increment, and decrement in the `finally`.
- **Pre-auth idle watchdog:** start an `asyncio` task that sleeps `PREAUTH_TIMEOUT` and, if `conn.session is None` and the socket is still open, closes it (cancel the watchdog once `conn.session` is set). Closes the "open a socket, send nothing" slow-loris that the frame budget alone misses.
- **Pre-auth frame budget:** count frames received while `conn.session is None`; over `MAX_PREAUTH_FRAMES` → `await ws.close(); break`.

Time-based per-IP **request** throttling (token bucket over time) is the
remaining DoS gap → documented residual + follow-up `applink_request_rate_limit`.

### 7. Audit logging (finding 8)

New module **`applink/audit.py`** — lazily configure one logger writing to the
(now `0o700`) runtime dir; `NullHandler` fallback on `OSError`:
```python
import logging
from pathlib import Path
from paths import ensure_secure_dir
_configured = False
def get_logger(sessions_dir: Path) -> logging.Logger:
    global _configured
    log = logging.getLogger("applink.audit")
    if not _configured:
        _configured = True
        try:
            ensure_secure_dir(sessions_dir)
            h = logging.FileHandler(sessions_dir / "applink_audit.log")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(h); log.setLevel(logging.INFO); log.propagate = False
        except OSError:
            log.addHandler(logging.NullHandler())
    return log
```
Wiring (single site): **`AppLinkServer.__init__`** does
`self._audit = audit.get_logger(paths.sessions_dir())` and passes `audit=self._audit`
into `FrameRouter`. Both the TUI (`applink_app.py:132`) and headless
(`headless.py:111`) build the server, so neither startup file changes.

- **`router.py`** `FrameRouter.__init__` gains `audit=None` (default
  `logging.getLogger("applink.audit")` so unit tests stay I/O-free). Emit
  `log.warning` on `AUTH_FAILED` (162), `PERMISSION_DENIED` (178), pairing
  failure/success (198/210), and the `spawn_tui`/pane-id rejections.
  **Never log a full secret** — `bearer[:8]`, device name, verb only; bad
  pairing token logs device + "invalid/expired" with no token bytes.
- **`server.py`** logs accept/close with `ws.remote_address`, and the
  cap/idle/per-IP rejections (the server has the socket; the router does not).

### 8. Deferred follow-ups (created at Step 8d as "after" mitigations)

`applink_cert_rotation`, `applink_bearer_rotation`, `applink_request_rate_limit`
(see `## Risk` → `### Planned mitigations`).

### 9. Documentation

- **New `aidocs/applink/security.md`** — threat-model note (current-state: trust
  boundary, hardening in place, residuals + deferred items). No change-history prose.
- **`protocol.md:206-209`** — the crypto review is no longer deferred; point to
  `security.md`; note the audit-log path + the new limits (current-state).
- **`CLAUDE.md`** applink section + `aidocs/applink/` pointer list — add `security.md`.

## Files touched

- `.aitask-scripts/applink/paths.py` — `ensure_secure_dir`
- `.aitask-scripts/applink/tls.py` — dir perms, TLS min-version + ciphers
- `.aitask-scripts/applink/sessions.py` — dir perms + `sessions.json` 0o600
- `.aitask-scripts/applink/router.py` — pane/window validators (all verbs), spawn_tui allowlist, string caps, audit hooks
- `.aitask-scripts/applink/server.py` — conn cap + per-IP cap + idle watchdog + frame budget + max_size/open_timeout + audit wiring
- `.aitask-scripts/applink/audit.py` — **new**
- `.aitask-scripts/monitor/monitor_core.py` — spawn_tui allowlist + send_keys/send_enter `--` (shared)
- `aidocs/applink/security.md` (new), `aidocs/applink/protocol.md`, `CLAUDE.md`

## Tests (each change owns its test)

- **`test_applink_router.sh`** (extend) — spawn_tui rejects shell-metachar
  `tui_name` (`board; rm -rf ~`, `$(...)`, `a|b`) → `ERR_BAD_PAYLOAD`, accepts a
  real registry name; malformed `pane_id` (`{mouse}`, `=s:w.p`, `-R`, ``) and
  `window_id` (not `@\d+`) rejected across **all** pane/window verbs incl.
  `restart_task`/`pick_next_sibling`/`kill_window`; `subscribe` drops/rejects
  non-`%\d+` entries and caps the list; oversized `keys`/`verb` rejected; injected
  audit logger records `AUTH_FAILED`, `PERMISSION_DENIED`, and the spawn_tui reject.
- **`test_applink_tls.sh`** (new) — `build_ssl_context` sets `minimum_version ==
  TLSv1_2` + cipher string; `ensure_cert` → key `0o600`, dir `0o700` (skip mode
  asserts on non-POSIX).
- **`test_applink_sessions.sh`** (new/extend) — `_save` leaves `sessions.json` `0o600`.
- **monitor test** (extend the file covering spawn_tui/send_keys) — `spawn_tui("x; rm -rf ~")`
  returns False and runs **no** tmux command (assert via a fake `tmux_run`); valid
  name builds the `new-window` argv; `send_keys` argv contains `--` before `keys`.
- **`test_applink_server`** (extend smoke/live) — `max_size`/`open_timeout` passed;
  >`MAX_CONNECTIONS` closed; >`MAX_PER_IP` from one IP closed while a second IP still
  connects; an unauthenticated idle socket is closed after `PREAUTH_TIMEOUT`;
  pre-auth flood past `MAX_PREAUTH_FRAMES` dropped.
- `shellcheck` any new `tests/*.sh`; keep the `assert_eq`/`assert_contains` harness.

## Verification

1. `for t in tls sessions router pusher content headless smoke; do bash tests/test_applink_$t.sh; done` + the monitor test — all PASS.
2. `bash tests/test_applink_headless_live.sh` — live `wss://` round-trip still pairs + keyframes under the hardened TLS context.
3. Manual: `ait applink`, pair, then confirm `applink_sessions/` is `0700`,
   `sessions.json` is `0600`, `applink_audit.log` shows a pairing line; send
   `spawn_tui {tui_name:"x; touch /tmp/pwned"}` and confirm rejection + that
   `/tmp/pwned` is absent; send `send_keys {keys:"-R"}` and confirm it is rejected
   (no terminal reset).

## Step 9 (post-implementation)

Profile 'fast' on current branch — no worktree/merge. Step 8d creates the three
deferred follow-ups. Archive via `./.aitask-scripts/aitask_archive.sh 985`. No
mobile (`../aitasks_mobile`) coordination needed — all changes are
server-internal; the wire-affecting work lives in the deferred bearer-rotation
follow-up.

## Risk

### Code-health risk: medium
- `monitor_core.spawn_tui` and `.send_keys` changes land in a path **shared with
  the desktop**; a regression hits the desktop too · severity: medium · → mitigation: in-task monitor tests (no-exec + argv assertions) — no separate task
- `server._handle` gains conn/per-IP caps, an idle watchdog, and a frame budget in
  the live connection lifecycle · severity: medium · → mitigation: in-task server tests covering each limit
- New audit file I/O in the runtime dir · severity: low · → mitigation: NullHandler fallback; router stays I/O-free in unit tests

### Goal-achievement risk: low
- Every area the task names is addressed; the deferred items (cert rotation,
  bearer rotation, time-based rate-limiting) are scoped with explicit user consent
  and tracked as after-mitigation follow-ups · severity: low · → mitigation: applink_cert_rotation, applink_bearer_rotation, applink_request_rate_limit
- TLS floor at 1.2 (not 1.3) could still allow a 1.2 suite — bounded by AEAD-only
  ciphers · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: after | name: applink_cert_rotation | type: enhancement | priority: medium | effort: medium | addresses: 10-year static self-signed cert residual | desc: re-mint the applink cert on a shorter validity near expiry, with a client re-pair flow for the changed fingerprint
- timing: after | name: applink_bearer_rotation | type: enhancement | priority: low | effort: medium | addresses: 7-day static bearer residual | desc: rotate the bearer on each resume to shorten a leaked bearer's useful life (wire-protocol + mobile-client change)
- timing: after | name: applink_request_rate_limit | type: enhancement | priority: medium | effort: medium | addresses: no time-based per-IP request throttling (only a concurrent per-IP cap ships in t985) | desc: add per-IP token-bucket throttling of authenticated requests/verbs to bound sustained abuse from a paired client

## Final Implementation Notes

- **Actual work done:** Implemented the full core hardening set exactly as planned, across 7 source files + a new `audit.py`, with 6 test suites (2 extended, 4 new). All 13 applink/monitor suites pass, including the live `wss://` round-trip under the hardened TLS context.
  - `tls.py`: `build_ssl_context` floors at TLS 1.2 + AEAD `set_ciphers`; `ensure_cert` uses `paths.ensure_secure_dir`.
  - `paths.py`: new `ensure_secure_dir` (mkdir + best-effort `chmod 0o700`).
  - `sessions.py`: `_save` secures the dir and `chmod 0o600`s `sessions.json` before the atomic rename.
  - `monitor_core.py`: `spawn_tui` now refuses names outside `TUI_NAMES` (closes the shell-command-execution sink at the source); `send_keys`/`send_enter` insert a `--` end-of-options separator.
  - `router.py`: `_req_pane_id`/`_req_window_id` validators applied to **every** pane/window verb (incl. the deferred `restart_task`/`pick_next_sibling`); `spawn_tui` allowlist + audit reject; string length caps; per-entry `%N` enforcement + cap on `subscribe`; injected `audit` logger emitting AUTH_FAILED / PERMISSION_DENIED / PAIR_* / SPAWN_TUI_REJECTED (bearer logged truncated only).
  - `server.py`: global + per-IP connection caps, pre-auth idle watchdog, pre-auth frame budget, `max_size`/`open_timeout` on `websockets.serve`, audit wiring (single config site in `__init__`, inherited by both TUI and headless paths).
  - `audit.py`: new lazy-configured `applink.audit` logger (FileHandler in the 0o700 runtime dir, NullHandler fallback).
- **Deviations from plan:** None of substance. One refinement during implementation: the `subscribe` branch was restructured with an `explicit` flag so an explicit-but-all-invalid pane list subscribes to *nothing* rather than falling through to the empty-list "subscribe to all" expansion (a latent correctness trap). Plan-externalization auto-scan missed the internal plan (recency window); re-run with `--internal` succeeded.
- **Issues encountered:** (1) The pusher test constructs `AppLinkServer` via `__new__` and needed the two new attributes (`_conns_by_ip`, `_audit`) plus a `logging` import. (2) The new router test block initially reused `full.bearer`, which the preceding `bye` test revokes — fixed by issuing fresh bearers in the block. (3) The server-limits "different IP admitted" check wrongly asserted `ws.closed` (a normally-finishing connection isn't server-closed) — changed to assert a CONN_ACCEPT audit line.
- **Key decisions:** TLS floor 1.2 not 1.3 (mobile-client compat); allowlist over shell-escaping for `spawn_tui` (stronger); directory `0o700` as the structural at-rest guard with file `0o600` as defense-in-depth; encryption-at-rest rejected (wrong layer for the same-host threat); concurrent per-IP cap shipped but time-based throttling deferred (honest residual + follow-up).
- **Upstream defects identified:** None. The reviewed weaknesses were all within this listener's own surface (no separate pre-existing bug in another script seeded them). The `spawn_tui` shell-command-execution sink and the uneven pane-id validation were original-design gaps in the t822_7 listener, addressed here directly (not pre-existing defects in unrelated code).
