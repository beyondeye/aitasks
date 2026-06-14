---
Task: t822_7_applink_websocket_listener.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_8_applink_snapshot_push_loop.md, aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md
Archived Sibling Plans: aiplans/archived/p822/p822_2_applink_tui_qr.md, aiplans/archived/p822/p822_3_monitor_port_design.md, aiplans/archived/p822/p822_6_extract_monitor_core.md
Base branch: main
---

# Plan: t822_7 — applink WebSocket listener (JSON control plane)

## Context

Parent **t822** is building `ait applink`, the bridge TUI that lets a mobile companion app drive an `ait` workspace (monitor-style) over a paired LAN WebSocket. Prior children landed: the protocol/permissions design docs (t822_1), the runnable TUI skeleton + QR pairing screen (t822_2), the monitor→applink port design (t822_3), and the `monitor_core.py` headless-core extraction (t822_6, just merged).

This task wires the **server side of the JSON control plane**: start a TLS WebSocket listener from the `ait applink` TUI, accept the `pair` verb, validate sessions, gate every subsequent command verb against a permission profile, and dispatch the allowed verbs into `monitor_core`. It is the first child that turns the pairing QR into a live connection.

**Explicitly out of scope** (each is a separate pending sibling): the binary snapshot/data plane (t822_8 push loop, t822_9 delta, t822_10 append), full multi-step modal handshakes incl. `pick_next_sibling`/`restart_task` mobile execution (t822_11), and syncing the canonical verb table back into `permissions.md` (t822_12). Those verbs return `UNKNOWN_VERB` here.

**Decisions confirmed with user:**
- TLS now: `wss://` with a persistent self-signed cert generated once via the system `openssl` binary (no new Python crypto dep); fingerprint computed with stdlib. A **security review/hardening follow-up** task is queued (see Risk → Planned mitigations).
- Build the profile-validator script (`aitask_applink_validate_profile.sh`) in this task.

**Repo is in separate-`aitask-data`-branch mode** (`aitasks/`, `aiplans/` are symlinks into `.aitask-data/`). Shared profile YAMLs commit via `./ait git`; runtime cert + session table are gitignored.

## Architecture

New WS server lives in the existing `.aitask-scripts/applink/` package, split so the **frame router is pure and unit-testable** (no sockets/tmux), and the transport/TLS/lifecycle wrap it:

```
applink_app.py (TUI)  ──starts──▶  server.AppLinkServer (websockets.serve + ssl)
                                        │ per-connection handler
                                        ▼
                                   router.FrameRouter  ── pure: (envelope, conn) → res/err
                                     ├─ sessions.SessionTable   (tokens, bearers, profiles, persist)
                                     ├─ profiles.ProfileGate    (applink_profiles/*.yaml → allow/deny)
                                     └─ monitor_core.TmuxMonitor (verb execution)
tls.CertManager  ── ensure self-signed cert (openssl), ssl.SSLContext, SHA-256/b64url fingerprint
```

Why this seam: `monitor_core` verbs need tmux and the transport needs a network/TLS stack, but **gating + routing + the pull-model confirm flow are pure logic** — isolating `FrameRouter` (duck-typed `monitor`) lets the bash test exercise pairing, auth, `PERMISSION_DENIED`, the confirm round-trip, and key translation with a stub monitor and zero sockets.

## Files to create

### `.aitask-scripts/applink/tls.py` — `CertManager`
- `ensure_cert(cert_dir: Path) -> tuple[Path, Path]`: if `server.crt`/`server.key` absent, shell out to `openssl req -x509 -newkey rsa:2048 -nodes -keyout … -out … -days 3650 -subj "/CN=ait-applink"` (encapsulate the call; raise a clear error if `openssl` missing). Idempotent — reuse on subsequent runs so the fingerprint is **stable across restarts** (mobile pins it for the pairing lifetime).
- `fingerprint(cert_path: Path) -> str`: stdlib only — read PEM, `ssl.PEM_cert_to_DER_cert`, `hashlib.sha256`, `base64.urlsafe_b64encode` (strip `=`). Matches protocol.md §Pairing flow step 2.
- `ssl_context(cert, key) -> ssl.SSLContext`: `PROTOCOL_TLS_SERVER` + `load_cert_chain`.
- Cert dir: `aitasks/metadata/applink_sessions/` (same gitignored, per-PC location as the session table).

### `.aitask-scripts/applink/sessions.py` — `SessionTable`
- In-memory **pairing tokens**: `mint_token()` (delegates to `pairing.generate_token`), `validate_and_consume(token)` with TTL (default 300 s) and **single-use** semantics (consumed token invalid even after later revoke — protocol.md).
- **Bearers**: `issue_bearer(profile, device) -> (bearer, expires_at)` (256-bit `secrets.token_urlsafe`), `lookup(bearer) -> Session|None`, `revoke(bearer)`, `revoke_all()`.
- `Session` dataclass: `bearer, profile, device_name, platform, created_at, expires_at, state`.
- **Persistence** to `aitasks/metadata/applink_sessions/sessions.json` (gitignored), rewritten on every issue/revoke (permissions.md §Storage). Load on startup so bearers survive a restart (`Suspended → resume`). Preserves the **stable-connection-ID invariant** from t822_2: regenerating the *pairing token* never touches issued bearers.

### `.aitask-scripts/applink/profiles.py` — `ProfileGate`
- `load(profiles_dir: Path)`: read `aitasks/metadata/applink_profiles/*.yaml` (`name`, `description`, `allowed_verbs`), tolerate a missing dir by falling back to built-in defaults.
- `is_allowed(profile_name, verb) -> bool`; `required_profile(verb) -> str|None` (lowest tier whose `allowed_verbs` contains the verb, tier order `read_only < monitor_control < full`) for the `PERMISSION_DENIED` `detail.required_profile`.

### `.aitask-scripts/applink/router.py` — `FrameRouter`
Pure dispatcher. `handle(envelope: dict, conn: ConnState) -> dict|None` returning the `res`/`err` frame (envelope `id` echoed). Logic:
1. Parse/validate envelope (`v,id,kind,verb,payload,auth`); malformed → `err BAD_PAYLOAD`.
2. `verb == "pair"`: ignore `auth`; `validate_and_consume(token)`; on success `issue_bearer(conn.selected_profile, device)`; reply `res {bearer, profile, expires_at}`; set `conn.state = Connected`. Invalid/expired token → `err AUTH_FAILED`.
3. Session verbs needing a valid bearer: `resume` (→ `Connected`, ok), `bye` (→ revoke + signal socket close). Missing/invalid bearer on any non-`pair` frame → `err AUTH_FAILED`.
4. Command verbs — auth check, then **profile gate** (`is_allowed`; deny → `err PERMISSION_DENIED detail.required_profile`), then dispatch to `monitor`:
   - `send_enter {pane_id}`, `send_keys {pane_id,keys,literal}`, `focus {pane_id,prefer_companion?}`→`switch_to_pane`, `cycle_compare_mode {pane_id}`, `spawn_tui {tui_name}`.
   - `forward_key {pane_id,key}` → `monitor.forward_key(pane_id, key)` (server-side translation, below).
   - `kill_pane {pane_id,confirmed}` → `kill_agent_pane_smart`; `kill_window {window_id,confirmed}` → `kill_window`. **Pull-model confirm**: `confirmed` falsy → `res {confirm_required:true, target:{…}}` (no execution); `confirmed:true` → execute. (Full multi-step handshakes are t822_11.)
   - `task_detail {task_id}` → `TaskInfoCache.invalidate` then `get_task_info`; reply the `TaskInfo` fields; gate `read_only`.
   - `pick_next_sibling`/`restart_task` → `err UNKNOWN_VERB` (`detail.reason:"deferred"`) per design-doc deferral.
   - unknown verb → `err UNKNOWN_VERB`.

### `.aitask-scripts/applink/server.py` — `AppLinkServer`
- `async start()/stop()`: `websockets.serve(handler, host, port, ssl=ctx)`; construct/own a `TmuxMonitor` (mirror `monitor_app.py:599` construction + `start_control_client()`), `SessionTable`, `ProfileGate`, `TaskInfoCache`, `FrameRouter`.
- Per-connection `handler(ws)`: maintain `ConnState` (state-machine per protocol.md: Discovering→Pairing→Connected→Suspended→Disconnected), JSON-decode frames, call `router.handle`, send replies; on `AUTH_FAILED` close after a short grace; on socket close with a still-valid bearer → `Suspended`.
- Expose `connection_state()` / `active_sessions()` + a change callback so the TUI can render live state.

### `.aitask-scripts/aitask_applink_validate_profile.sh` — profile validator
Mirror an existing simple validator script's shell conventions. Validates one `applink_profiles/<name>.yaml`: `name` matches filename stem, no duplicate `allowed_verbs`, every verb ∈ the dispatcher's registered verb set. Source the verb set from a single Python helper in `router.py` (e.g. `KNOWN_VERBS`) invoked via the ait python — **one source of truth**, no hand-copied list. Referenced by permissions.md §Adding a new profile step 2.

### `aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml`
Cumulative `allowed_verbs` per the canonical table in `monitor_port_design.md` (the superseding source):
- `read_only`: `snapshot`, `task_detail`
- `monitor_control`: + `send_enter`, `send_keys`, `forward_key`, `focus`, `cycle_compare_mode`
- `full`: + `kill_pane`, `kill_window`, `spawn_tui`

(`pair`/`resume`/`bye` are session-management, not profile-gated, so they are intentionally absent. `subscribe`/`request_keyframe`/data-plane verbs arrive with t822_8.)

### `tests/test_applink_router.sh`
Self-contained bash test driving an inline Python harness against `FrameRouter` with a **stub monitor** (records calls) — no sockets, no tmux, no TLS:
- pair with valid token → `res` carries bearer+profile; token now single-use (replay → `AUTH_FAILED`).
- command frame with no/invalid bearer → `AUTH_FAILED`.
- `read_only` session calling `send_keys` → `PERMISSION_DENIED` with `detail.required_profile:"monitor_control"`.
- `kill_pane confirmed:false` → `confirm_required:true`, monitor **not** called; `confirmed:true` → `kill_agent_pane_smart` invoked.
- `forward_key` translation: `"up"`→`Up`, `"ctrl+c"`→`C-c`, `"a"`→ literal.
- `pick_next_sibling` → `UNKNOWN_VERB`.
Plus a `tls.py` assertion: `fingerprint()` is deterministic for a fixed cert.

## Files to modify

### `.aitask-scripts/monitor/monitor_core.py` — host the key map server-side (per design doc)
- Move `_TEXTUAL_TO_TMUX` (currently `monitor_app.py:107`) here and add `translate_key(key, character=None) -> tuple[str,bool]|None` returning `(tmux_keys, literal)`: special-key map → `(mapped, False)`; `ctrl+x` → `("C-x", False)`; else a single char → `(char, True)`; otherwise `None`.
- Add `TmuxMonitor.forward_key(pane_id, key, character=None) -> bool`: `translate_key` then `send_keys`; `None` → return `False`.

### `.aitask-scripts/monitor/monitor_app.py` — delegate, keep desktop behavior identical
- Replace the local `_TEXTUAL_TO_TMUX` dict with a **re-export import** from `monitor_core` (`from monitor_core import _TEXTUAL_TO_TMUX`) so any other reader and existing semantics are preserved (blast-radius guard).
- Rewrite `_forward_key_to_tmux` (`:1354`) to call `self._monitor.forward_key(pane_id, event.key, event.character)` — same three-branch outcome, now sourced from the shared translator. The refresh calls (`call_later(self._fast_preview_refresh)`) stay in the app.

### `.aitask-scripts/applink/pairing.py` — real fingerprint
- Replace the `compute_self_signed_fingerprint()` stub (returns `"NOT-IMPLEMENTED"`) with a thin call into `tls.CertManager` (ensure cert, return its fingerprint). Single-function swap, exactly as the t822_2 notes anticipated.

### `.aitask-scripts/applink/applink_app.py` — lifecycle + live status
- On `on_mount`: start `AppLinkServer` as a Textual worker/asyncio task; pass the chosen profile (the QR-time profile selector — minimal: default `monitor_control`, with a follow-up note if a richer selector is wanted) into the server's pairing context.
- `StatusScreen`: replace the placeholder with live connection state (Discovering/Pairing/Connected/Suspended/Disconnected) + connected device name(s), refreshed via the server callback.
- `PairingScreen.action_regenerate` (`r`): in addition to rotating the unused pairing token, **revoke active bearers** (protocol.md `r` = revoke/new-QR) via `server.revoke_all()`; preserves the documented invariant that regenerate rotates the *token* — revoke is the explicit destructive half of the same key.
- On unmount/quit: `await server.stop()`.

### `.aitask-scripts/aitask_applink.sh` — dependency check
- Add `websockets` to the `missing=()` import probe alongside `textual`/`segno`.

### `.aitask-scripts/aitask_setup.sh` — new dependency
- Append `'websockets>=12,<17'` to `AIT_PIP_SPECS_CPYTHON_EXTRA` (`:26`) and `websockets` to `AIT_IMPORTS_CPYTHON_EXTRA` (`:28`). (CPython-only — applink never runs under the PyPy board fast-path.)

### gitignore (data-branch aware)
- Ignore the runtime dir `aitasks/metadata/applink_sessions/` (cert + key + `sessions.json`). In data-branch mode this resolves under `.aitask-data/`; add the entry to the gitignore that governs `aitasks/metadata/` (verify which at implementation time — `.aitask-data/.gitignore` vs `seed/aitask_scripts_gitignore.seed`). The `applink_profiles/` dir is **committed** (shared config), so ignore only `applink_sessions/`.

## Trade-offs & rejected alternatives
- **`websockets` lib vs hand-rolled RFC 6455:** chose the library — masking/fragmentation/close/permessage-deflate are error-prone by hand, and the lib is async-native and integrates with Textual's asyncio loop. Cost: one new CPython dependency.
- **openssl shell-out vs `cryptography` lib:** chose openssl (user-confirmed) — avoids a heavy new Python dep; openssl is ubiquitous on dev machines. Cost: an external-binary dependency (guarded with a clear error).
- **Pure `FrameRouter` vs routing inside the socket handler:** chose the pure split for testability and so t822_8/t822_11 can extend dispatch without touching transport. Cost: a little more structure now.
- **Runtime state under `aitasks/metadata/` vs a repo-root `.aitask-applink/`:** kept the doc-specified `aitasks/metadata/applink_sessions/` path (permissions.md contract, mobile-facing) and gitignored it, rather than inventing a new root dir.

## Verification
1. `bash tests/test_applink_router.sh` → PASS (pairing, auth, gating, confirm pull-model, key translation, deferred verbs).
2. `bash tests/test_applink_smoke.sh` → still PASS (TUI boots headlessly).
3. `shellcheck .aitask-scripts/aitask_applink.sh .aitask-scripts/aitask_applink_validate_profile.sh` → clean.
4. `./.aitask-scripts/aitask_applink_validate_profile.sh aitasks/metadata/applink_profiles/full.yaml` → OK; a hand-broken YAML (bogus verb / dup / name mismatch) → non-zero with a clear message.
5. Live end-to-end with a synthetic client (real mobile app lives in `../aitasks_mobile`, unavailable here): `./ait applink`, scan/copy the QR values, connect a `python -m websockets` (or a tiny script pinning the cert fingerprint) to `wss://<ip>:<port>/`, send `pair` → receive bearer+profile; exercise an allowed verb (`send_keys` reaching a live tmux pane) and a disallowed one (`PERMISSION_DENIED`); press `r` in the TUI → next frame from the old bearer gets `AUTH_FAILED`.
6. `./ait monitor` still forwards keystrokes into a focused pane (regression check for the `_TEXTUAL_TO_TMUX` move).
7. Fresh `ait setup` on a clean venv installs `websockets` without error.

## Risk

### Code-health risk: medium
- Moving `_TEXTUAL_TO_TMUX` + key translation out of `monitor_app.py` touches the **live desktop key-forward path** (load-bearing: typing into panes from `ait monitor`). A regression breaks interactive use. · severity: medium · → mitigation: re-export alias + thin delegation keep behavior identical; covered by Verification #6 and the router key-translation test.
- A new **TLS network listener is fresh attack surface** (token/bearer handling, cert lifecycle, DoS, input validation) shipped without a dedicated security review. · severity: high · → mitigation: applink_security_review_hardening
- New `websockets` dependency + reliance on the system `openssl` binary. · severity: low · → mitigation: TBD (import probe in launcher; guarded openssl error).

### Goal-achievement risk: medium
- The **real mobile client is in a separate repo and unavailable** here, so end-to-end pairing is only exercised against a synthetic client — payload-schema drift from what mobile expects is possible. · severity: medium · → mitigation: strict adherence to the `monitor_port_design.md` payload schemas; documented in Notes for sibling tasks for the mobile mirror.
- Several verbs (`pick_next_sibling`, `restart_task`, full modal handshakes, data plane) are **intentionally deferred** to siblings — partial surface by design, not a gap. · severity: low · → mitigation: TBD (explicit `UNKNOWN_VERB`/scoping; covered by tests).

### Planned mitigations
- timing: after | name: applink_security_review_hardening | type: chore | priority: high | effort: medium | addresses: code-health "new TLS network listener is fresh attack surface" | desc: Security review + hardening of the applink WS listener — TLS suite/cert rotation & lifecycle, bearer entropy/expiry, pairing-token replay, connection/DoS limits and rate-limiting, strict payload validation, and denied-verb audit logging.

## Step 9 (Post-Implementation)
Standard task-workflow Step 9: commit on current branch (profile `fast`, no worktree) — code via `git`, profile YAMLs via `./ait git`; push via `./ait git push`; archive via `./.aitask-scripts/aitask_archive.sh 822_7`. Parent t822 keeps t822_8..t822_13 pending — archival closes only this child. The `applink_security_review_hardening` "after" mitigation is created at Step 8d.

## Out of scope / noted follow-ups
- Binary snapshot/data plane and `subscribe`/`focus`-cadence (t822_8/9/10); full modal handshakes incl. `pick_next_sibling`/`restart_task` execution (t822_11); syncing the verb table into `permissions.md` (t822_12); headless `--headless-for-applink` mode (t822_13).
- Seeding `applink_profiles/*.yaml` into `seed/` for fresh installs — small follow-up if not folded into t822_12's "ship matching YAML updates".
- A richer QR-time profile selector in the TUI (v1 defaults to `monitor_control`).
