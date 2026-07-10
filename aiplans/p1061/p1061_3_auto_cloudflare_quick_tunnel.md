---
Task: t1061_3_auto_cloudflare_quick_tunnel.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_1_*.md, aiplans/archived/p1061/p1061_2_*.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-10 10:28
---

# Plan: A3 — Auto-spawned Cloudflare Quick Tunnel (t1061_3)

## Context

A3 of the t1061 paired decomposition (parent plan
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md` §"Endpoint &
trust model" is normative). Turnkey Phase 2: `ait applink` spawns and
supervises `cloudflared` itself, parses the generated `*.trycloudflare.com`
URL, and emits it as a `kind=tunnel, trust=ca` endpoint in the pairing QR
alongside the LAN endpoint. `tunnel_howto.md:178` already forward-links this
task as the turnkey variant of Recipe 3.

**Dependency status (verified 2026-07-09):**
- A1 (`t1061_1`) — ARCHIVED. Landed the full emission layer in
  `pairing.py`: `Endpoint` (`:63`), `ResolvedAdvertise(primary, alts,
  warning, override)` (`:77`), `resolve_advertised_endpoints` (`:212`),
  `encode_alt_param` (`:198`), `build_pairing_uri(kind/trust/alt)` (`:299`),
  `normalize_advertised_host` (`:94`); four `tmux.applink.advertised_*`
  config keys in `server.load_applink_config()` (`server.py:63-131`); four
  `--advertise-*` flags on both entry points.
- A2 (`t1061_2`) — ARCHIVED. `aidocs/applink/tunnel_howto.md` exists;
  Recipe 3 marked "gated on `aitasks_mobile#31_3`".
- **Cross-repo M2+M3 (`aitasks_mobile#31_2`, `#31_3`) — BOTH ARCHIVED.**
  Client parses `alt`, races endpoints, accepts per-endpoint `trust=ca`
  (CA-consent dialog at pair time). The xdep gate is satisfied. Mobile
  `t31_5` (pending) is the on-device CA-trust tunnel verification that will
  exercise this task's output end-to-end.
- `cloudflared` is NOT installed on this machine — Step 1 downloads the
  official standalone linux-amd64 binary (no root needed).

## Primary-endpoint decision (recorded per task AC)

**Primary = LAN/pin; tunnel endpoint goes in `alt`.** Old clients scanning
the QR keep working (they read only the authority and pin-verify); M2+
clients parse `alt`, race, and prefer LAN when co-located. No "remote-first
QR" toggle in this task — the racing client makes it unnecessary; revisit
only if a real need appears.

## Steps

### 1. Origin-TLS verification FIRST (gate for the rest of the plan)

The applink origin is `wss://` with a self-signed, no-SAN cert
(`tls.py:32` `/CN=ait-applink`, `openssl req -x509` with no `-addext
subjectAltName`); cloudflared validates origin certs by default.

- Download the official `cloudflared` linux-amd64 binary (GitHub releases)
  into the scratchpad; `chmod +x`.
- Start the applink server headless on a test port; run
  `cloudflared tunnel --url https://localhost:<port> --no-tls-verify`.
- Confirm end-to-end through the tunnel: an HTTPS request answered by the
  applink server AND a **WebSocket upgrade** completing against
  `wss://<x>.trycloudflare.com` (small asyncio/websockets probe driving the
  pair path).
- **Note:** this briefly exposes the local test server behind an ephemeral
  public hostname (bearer/pairing gating still applies); tunnel is torn
  down right after the probe.
- **Failure = HARD STOP / replan point (not a silent fallback).** Named
  tunnels are a materially different product shape (account credentials,
  config file, stable tunnel identity, different invocation, URL discovery,
  and different docs/security expectations) — they are NOT specified by
  this plan. If the quick-tunnel probe fails: record the empirical findings
  as a deviation in this plan, do **not** proceed to Steps 2-7, and return
  to the plan checkpoint for an explicit re-plan (the named-tunnel variant
  needs its own specified design: config/credential handling, lifecycle,
  URL discovery, tests, docs).

### 2. Tunnel supervisor — new `.aitask-scripts/applink/tunnel.py`

Textual-free (shared by TUI + headless; `test_applink_headless.sh` asserts
no-Textual). Pure parsing + asyncio supervision:

- `find_cloudflared() -> str | None` — `shutil.which("cloudflared")`.
- `parse_tunnel_url(line: str) -> str | None` — pure; extract
  `https://<x>.trycloudflare.com` from a cloudflared output line.
- `QuickTunnel` supervisor — pattern mix of
  `monitor_core.TmuxControlClient.start()` (`monitor_core.py:425-457`,
  asyncio `create_subprocess_exec` + reader task parsing lines) and
  `pusher.PushScheduler` start/stop/cancel shape (`pusher.py:99-137`):
  - `start()` spawns `cloudflared tunnel --url https://localhost:<port>
    --no-tls-verify` (stderr piped — cloudflared logs there), reader task
    scans for the URL, state machine `starting → up | failed`, `stopped`
    on shutdown.
  - `await wait_url(timeout)` for emission call sites.
  - `stop()` — terminate → bounded wait → kill; suppress CancelledError.
  - `state` + `url` + `on_change` callback for status surfaces.
- **Ownership:** `AppLinkServer` gains an optional tunnel backend param;
  `start()` (`server.py:186-207`) spawns the supervisor after the listener
  binds; `stop()` (`server.py:209-220`) tears it down; tunnel state changes
  fire the existing `_notify()`/`on_change` seam (`server.py:398`) that the
  TUI already polls. Single lifecycle owner serves both entry points, and
  the server knowing tunnel-active is what gates the Step-5 cap exemption.

### 3. QR emission (per A1 grammar)

- Tunnel endpoint = `Endpoint("<x>.trycloudflare.com", 443, "tunnel", "ca")`.
- New pure helper in `pairing.py`:
  `merge_tunnel_endpoint(resolved: ResolvedAdvertise, tunnel: Endpoint | None)
  -> ResolvedAdvertise` — appends the tunnel endpoint to `alts` (after any
  existing entries, e.g. a user-advertised override's LAN alt) and marks the
  result so `alt=` is emitted. Emission rule: emit `alt` when alts are
  non-empty; primary params (`kind`/`trust`) stay gated on `override`
  exactly as today → **no tunnel and no override ⇒ byte-identical legacy
  QR** (pinned by negative-control test).
- If the user also set `advertised_*`, their primary is untouched; the
  tunnel is an additional alt.
- **Dynamic recomputation on EVERY emit path (the tunnel URL arrives
  seconds after startup — no emit may close over a stale snapshot):**
  - **Merge at build time, not resolve time.** The once-resolved
    `ResolvedAdvertise` stays cached (it is static config); the tunnel
    endpoint is merged **inside each URI build**, reading the supervisor's
    *current* state:
    - TUI: `AppLinkRuntime.build_uri()` (`applink_app.py:134-145`) merges
      `merge_tunnel_endpoint(self.advertised, server.tunnel_endpoint())`
      before calling `build_pairing_uri`. Every existing `build_uri()`
      caller (compose, `regenerate`) then picks up the tunnel for free.
      **Startup-order guard:** `PairingScreen` is pushed *before*
      `_start_server()` creates `runtime.server` (`on_mount` at
      `applink_app.py:538` pushes, `:539` starts the worker; `self.server`
      is `None` until `create_server` at `:163`, and stays `None` on the
      `--smoke` path). `build_uri()` must treat `self.server is None` (or
      no supervisor / no URL yet) as "no tunnel endpoint" and emit the
      existing LAN/config QR unchanged; the later tunnel state change then
      refreshes via `set_data()` with the merged tunnel alt.
    - Headless: `_emit()` (`headless.py:158-167`) currently closes over the
      once-resolved `adv` — change it to compute
      `merged = merge_tunnel_endpoint(adv, server.tunnel_endpoint())` at
      **each call**, so the SIGHUP `_reprint` (and the post-`wait_url`
      initial emit) always reflect live tunnel state, including
      tunnel-came-up-after-timeout.
  - Headless startup: when auto-tunnel is on, `serve()` waits
    `wait_url(timeout≈15s)` before the first `_emit()`; on timeout it
    emits the current (LAN-only) block plus a fail-visible warning line
    (A1's warning pattern) telling the user to SIGHUP once the tunnel URL
    line appears.
  - **TUI QR re-render (explicit path — the QR is built once in
    `PairingScreen.compose()` at `applink_app.py:343` and nothing
    refreshes it today):** tunnel state change → server `_notify()` →
    `ApplinkApp._on_server_change()` (`applink_app.py:560-564`) gains a
    PairingScreen branch: when `self.screen` is a `PairingScreen`, call
    `screen._qr.set_data(self.runtime.build_uri())` (`_on_server_change`
    is a method on `ApplinkApp` itself — `self.runtime`, not
    `self.app.runtime`)
    (`TerminalQR.set_data`, `qr_widget.py:40-43` — same mechanism as the
    `r` regenerate action at `applink_app.py:391-396`; token unchanged,
    only endpoints refresh). `_refresh_advisory` shows the tunnel status
    line via its existing 2s poll.
  - **Focused verification for delayed tunnel-up (both surfaces):** test a
    supervisor whose fake cloudflared prints the URL only after the first
    emit — assert the headless SIGHUP reprint now contains the tunnel alt,
    and (Textual-guarded) that `_on_server_change` updates the mounted
    PairingScreen QR payload.

### 4. Surfaces

- Config: `tmux.applink.auto_tunnel: cloudflared` — string naming the
  backend (only `cloudflared` accepted for now); fault-tolerant parse block
  in `load_applink_config()` mirroring `advertised_kind`
  (`server.py:111-116`). Document in `seed/project_config.yaml:382-441`
  block + live `aitasks/metadata/project_config.yaml`.
- CLI: `--auto-tunnel` flag on both argparsers (`applink_app.py:581-601`,
  `headless.py:258-282`); flag ⇒ backend `cloudflared`; CLI overrides
  config (consistent with A1's group precedence spirit).
- TUI status: tunnel line in `PairingScreen._refresh_advisory()` lines +
  `DevicesScreen._refresh()` listener line — states: starting / up
  (hostname shown) / failed / binary missing.
- Headless: tunnel state + URL line printed after the pairing block.
- Binary missing (or spawn/parse failure) with auto-tunnel enabled →
  fail-visible warning on both surfaces, server keeps serving LAN-only
  (never a hard exit — same rationale as A1's invalid-config fallback).

### 5. MAX_PER_IP loopback exemption (deliberate)

All tunneled connections arrive from `127.0.0.1` (cloudflared → localhost),
sharing one `MAX_PER_IP = 8` bucket (`server.py:45`, enforced at
`server.py:233-240`): 3-4 racing/reconnecting devices could exhaust it.
**Decision: exempt loopback sources from the per-IP cap only while the
tunnel supervisor is active** (server owns both, so the gate is local);
global `MAX_CONNECTIONS = 64` and all pre-auth limits still bound loopback.
Audit-log reason string unchanged for non-loopback. Negative controls:
cap still enforced for loopback when tunnel inactive, and for non-loopback
always.

### 6. Docs

- Extend `aidocs/applink/tunnel_howto.md` Recipe 3 with the auto-spawn
  turnkey variant (config key + flag + status line); keep the
  classify-by-cert table row in sync.
- **Update the three "gated on `aitasks_mobile#31_3`" qualifiers — with
  verified cross-repo state, keeping wording conditional on the app
  build.** Verified 2026-07-09 against the linked repo (`ait projects
  resolve aitasks_mobile` → `../aitasks_mobile`): `t31_2` (multi-endpoint
  + racing) and `t31_3` (per-endpoint CA trust, incl. CA-consent pairing
  dialog) are both **archived** — code landed. However `t31_5` (on-device
  CA-trust tunnel verification) is still **pending**, and users may run
  app builds predating M3. So do NOT flip to unconditional "works today":
  rephrase from "gated on `aitasks_mobile#31_3` landing" to "requires an
  app build that includes per-endpoint CA trust (`aitasks_mobile#31_3`);
  older builds pin-verify and fail with a pin mismatch (expected)". Sites:
  `tunnel_howto.md` (Recipe 3 + table + troubleshooting), `protocol.md`
  Phase-2 TLS-trust cell + Phase-1 bullet, `protocol.md` "Endpoint & trust
  model" inert-`trust=ca` note.
- Security notes (task AC): ephemeral public hostname; bearer + permission
  profiles still gate every verb; recommend t1068 (request rate-limit) for
  sustained use; loopback-bounded `--no-tls-verify` documented as an
  accepted, bounded trust step.

### 7. Tests — new `tests/test_applink_tunnel.sh`

Bash + Python-heredoc `check()` pattern (model:
`tests/test_applink_advertise.sh`):
- `parse_tunnel_url`: **strict — accept ONLY
  `https://<sub>.trycloudflare.com` hostnames.** Fixtures modeled on real
  cloudflared log shape, including unrelated URLs before and after the
  tunnel line (`https://developers.cloudflare.com/...` docs links, the
  `127.0.0.1:<port>/metrics` address, `https://www.cloudflare.com/...`)
  — assert none of them match and the trycloudflare URL does; also: no-URL
  input → None; first trycloudflare match wins; lookalike rejects
  (`evil-trycloudflare.com`, `trycloudflare.com.evil.net`).
- `QuickTunnel` supervision against a **fake cloudflared script** (prints a
  trycloudflare URL then sleeps): state transitions, `wait_url`, timeout
  path (script that never prints), clean shutdown kills the child, `stop()`
  idempotent.
- Delayed tunnel-up (per Step 3): fake binary printing the URL after the
  first emit — headless SIGHUP reprint gains the tunnel alt;
  Textual-guarded `_on_server_change` → mounted PairingScreen
  `TerminalQR.set_data` payload assertion.
- `merge_tunnel_endpoint` + emission: exact `alt` grammar
  (`<x>.trycloudflare.com:443;tunnel;ca`), appended after existing alts;
  negative control — no tunnel + no override ⇒ byte-identical legacy URI.
- Config: `auto_tunnel` parse + per-key fault tolerance; argparse
  `--auto-tunnel` accepted on both real entry points.
- Extend `tests/test_applink_server_limits.sh`: loopback exemption when
  tunnel active + both negative controls (loopback w/o tunnel; non-loopback
  with tunnel).

## Verification

- Step 1 empirical origin-TLS + WebSocket-through-tunnel probe (live,
  in-session, mandatory before UI work).
- `bash tests/test_applink_tunnel.sh`, `test_applink_server_limits.sh`,
  `test_applink_advertise.sh`, `test_applink_pairing.sh`,
  `test_applink_headless.sh`, `test_applink_smoke.sh` all green.
- Live e2e with an M2+M3 client (QR scan, racing prefers LAN co-located):
  mobile `t31_5` covers on-device; offer a Step-8c manual-verification
  follow-up on this side for the spawn→QR→pair flow.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9 (fast profile —
current branch, no worktree/merge).

## Risk

### Code-health risk: medium
- Server lifecycle coupling: tying supervisor spawn/teardown into
  `AppLinkServer.start()/stop()` touches the load-bearing listener path ·
  severity: medium · → mitigation: covered in-plan (supervisor isolated in
  new Textual-free module with PushScheduler-shaped stop/cancel; spawn
  strictly after bind; failure degrades to LAN-only warning, never blocks
  serving; supervision unit-tested with fake binary).
- Admission-cap change: loopback exemption alters the t1007 DoS-caps
  surface · severity: medium · → mitigation: covered in-plan (exemption
  gated on tunnel-active only, `MAX_CONNECTIONS` + pre-auth limits still
  bound loopback; two negative-control tests pin the unchanged paths).
- Emission change: `alt` now emittable without `override` · severity: low ·
  → mitigation: covered in-plan (byte-identical legacy QR negative control;
  pure `merge_tunnel_endpoint` helper keeps the resolver untouched).

### Goal-achievement risk: medium
- Empirical feasibility: quick tunnels may fail to proxy the self-signed
  no-SAN `wss://` origin despite `--no-tls-verify` · severity: medium ·
  → mitigation: covered in-plan (Step 1 is a mandatory first gate; on
  failure it is a HARD STOP back to the plan checkpoint with a recorded
  deviation — no under-specified named-tunnel implementation proceeds
  under this plan).
- Stale-QR emission: the tunnel URL arrives async; any emit path closing
  over a pre-tunnel snapshot shows a scannable QR without the tunnel ·
  severity: medium · → mitigation: covered in-plan (merge-at-build-time on
  every emit path — `build_uri()` + headless `_emit()` — plus the focused
  delayed-tunnel-up tests on both surfaces).
- Live phone e2e cannot run in this session · severity: low · → mitigation:
  covered in-plan (mobile `t31_5` pending on-device verification; Step-8c
  manual-verification follow-up offered here).

### Planned mitigations
None — all risks are covered in-plan (Step-1 empirical gate with fallback,
negative-control tests, fail-visible degradation); no separate before/after
mitigation tasks proposed.
