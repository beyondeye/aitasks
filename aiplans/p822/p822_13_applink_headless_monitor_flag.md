---
Task: t822_13_applink_headless_monitor_flag.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_14_applink_push_scheduler_resilience.md
Archived Sibling Plans: aiplans/archived/p822/p822_6_extract_monitor_core.md, aiplans/archived/p822/p822_7_applink_websocket_listener.md, aiplans/archived/p822/p822_8_applink_snapshot_push_loop.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_13 — applink `--headless-for-applink` mode for `aitask_monitor.sh`

## Context

Parent **t822** builds `ait applink`, the bridge that lets a mobile companion
drive an `ait` workspace over a paired LAN WebSocket. The control plane (t822_7)
and the Stage-1 binary data plane (t822_8) landed inside the **Textual TUI**
`ait applink`: `AppLinkRuntime`/`ApplinkApp` (in `applink_app.py`) build the
session table, cert, profile gate, pairing token + QR, and start
`AppLinkServer` as a Textual worker.

This task (final §"Deferred follow-up tasks" bullet of
`aidocs/applink/monitor_port_design.md`) adds a **headless** way to run the same
bridge on a box nobody is watching — `ait monitor --headless-for-applink` —
skipping Textual entirely and serving only the applink listener + push loop.

The key enabling fact, verified on-disk: the whole server stack is already
**Textual-free** — `server.py`, `router.py`, `pusher.py`, `sessions.py`,
`profiles.py`, `tls.py`, `pairing.py`, `paths.py`, and `monitor_core.py` contain
**no** `import textual`. Only `applink_app.py` (and `qr_widget.py`) import
Textual. So a headless runner that imports the server stack directly — **never**
`applink_app.py` — gives us a no-Textual entry point for free. `AppLinkServer`
already owns its own `TmuxMonitor`, control client, and per-connection
`PushScheduler` with clean async `start()`/`stop()`; the headless runner just
has to build the four collaborators, start the server, render pairing info to
stdout, and idle until a signal.

**Pairing in headless mode (the design decision the task asks us to make and
document):** there is no TTY to press `r`, so the runner **prints the
`applink://…` pairing URI + the cert fingerprint + an ASCII QR (via `segno`,
already an applink dep) to stdout** at startup. Re-pairing without restarting is
handled by **`SIGHUP` → mint a fresh pairing token + reprint** (this reuses
`SessionTable.mint_pairing_token`, which is exactly the TUI "regenerate"
semantics and preserves the t822_2 stable-connection-ID invariant: rotating the
token never touches issued bearers). `SIGINT`/`SIGTERM` shut the server down
cleanly. Already-paired bearers persist in `sessions.json` across restarts
(Suspended → resume), so an unattended box keeps its devices.

**Repo is in separate-`aitask-data`-branch mode.** Profile `fast`, current
branch (no worktree). No task/plan-data file changes here other than the plan
itself (committed via `./ait git`); all code commits via plain `git`.

## Files to create

### `.aitask-scripts/applink/headless.py` (NEW — the Textual-free runner)

Imports only the Textual-free siblings (`server`, `sessions`, `profiles`, `tls`,
`pairing`, `paths`) plus `segno`, `asyncio`, `argparse`, `signal`, `io`,
`socket`, `sys`. It **must not** import `applink_app` or `qr_widget` (both pull
in Textual) — this is the load-bearing contract, asserted by the test below.
(`socket` is needed for `socket.gethostname()`; we import it directly rather
than reuse `applink_app._hostname`, which lives in the Textual module.)

Structure (mirrors what `AppLinkRuntime.create_server` + `ApplinkApp._start_server`
do, minus Textual):

- **`render_pairing_block(uri, fingerprint, *, show_qr=True) -> str`** — PURE,
  no I/O. Returns the multi-line stdout block: a header, the `Fingerprint: …`
  line, the `Pair URL: <uri>` line, a short hint, and (unless `show_qr` is False)
  the ASCII QR. Render the QR with `segno.make(uri).terminal(out, border=1)`
  into an `io.StringIO()` and append its `getvalue()` — keeping this a pure
  string-builder is what makes it unit-testable without a socket. (`segno`'s
  `terminal(out, border, compact)` signature confirmed on-disk.)

- **`async def serve(*, port, profile, show_qr) -> int`** — the runner body.
  **Validate inputs BEFORE any state-mutating side effect** (no token mint, no
  cert generation, no socket bind until the profile name is known-good):
  1. `profile_gate = ProfileGate.load(profiles_dir())`. Validate `profile`
     against `profile_gate.names()`; if unknown, print the valid names to stderr
     and `return 2` (distinct reason — reject unresolvable input rather than
     silently defaulting). **This runs first, before minting the pairing token
     or generating the cert, so a `--profile` typo fails clean with zero side
     effects.**
  2. `cert = CertManager(sessions_dir())`; try `fingerprint = cert.fingerprint()`
     and `ssl_ctx = cert.ssl_context()`. On `CertError`/`OSError`, print a clear
     error to stderr and `return 1` (no plaintext fallback — `wss://` is the
     baseline, matching `server.start()`'s own refusal).
  3. `session_table = SessionTable(sessions_dir())`;
     `token = session_table.mint_pairing_token()` (only now that the profile is
     validated and the cert exists).
  4. Build `AppLinkServer(session_table=…, profile_gate=…, ssl_context=ssl_ctx,
     port=port, pair_profile=profile, on_change=None)`; `await server.start()`.
     If `server.error` is set, print it to stderr and `return 1`.
  5. Compute `uri = build_pairing_uri(token, detect_lan_ip(), port, fingerprint,
     socket.gethostname())` and `print(render_pairing_block(uri, fingerprint,
     show_qr=show_qr), flush=True)`.
  6. Install loop signal handlers: `SIGINT`/`SIGTERM` set an `asyncio.Event`
     (`stop`); `SIGHUP` re-mints the token, recomputes the URI, and reprints the
     block (best-effort; guard with try/except so a reprint failure never kills
     the server). Use `loop.add_signal_handler` (POSIX; the bridge is
     Linux/macOS only).
  7. `await stop.wait()`; in `finally`, `await server.stop()`; `return 0`.

  Keep the profile-name check a plain `profile in profile_gate.names()`
  membership test (no socket/cert needed to reach it) so the test in §A.4 below
  can exercise the rejection path directly. Reference `CertManager` and
  `SessionTable` as **module-level names** (the existing `from tls import
  CertManager` / `from sessions import SessionTable`) and construct them inside
  `serve()` — so a test can monkeypatch `headless.CertManager` /
  `headless.SessionTable` to spies and prove neither is constructed on the
  bad-profile path. `ProfileGate.load(profiles_dir())` only reads YAML (no token,
  no cert, no socket), so doing it first is side-effect-free.

- **`main(argv=None) -> int`** — `argparse` with `prog="ait monitor
  --headless-for-applink"`, a description naming this as the unattended applink
  bridge, and flags:
  - `--port` (int, default `DEFAULT_PORT` imported from `server`),
  - `--profile` (default `DEFAULT_PAIR_PROFILE` imported from `server`),
  - `--no-qr` (store_true; print URL+fingerprint only — for log redirection).
  Then `return asyncio.run(serve(port=…, profile=…, show_qr=not args.no_qr))`.
  `if __name__ == "__main__": sys.exit(main())`.

### `tests/test_applink_headless.sh` (NEW — unit/contract + launcher routing)

Self-contained bash test (model: `test_applink_smoke.sh` / `test_applink_pairing.sh`),
skips gracefully if deps absent. Two groups:

**A. Pure/contract assertions (no socket):**
1. **No-Textual contract (the core guard):** in a subprocess,
   `import applink.headless` (with `.aitask-scripts` on `sys.path`) then
   `assert 'textual' not in sys.modules` — fails loudly if the runner ever grows
   a Textual import. Skip if `websockets`/`msgpack`/`segno` missing.
2. **`render_pairing_block` is pure + correct:** returns a `str` containing the
   `applink://` URI and the fingerprint; with `show_qr=False` it contains no QR
   block; with `show_qr=True` it is strictly longer (QR appended). No socket, no
   cert.
3. **`headless.main(["--help"])`** exits 0 and the help text mentions `--port` /
   `--profile` / `--no-qr` (argparse `SystemExit(0)` caught).
4. **Unknown `--profile` is rejected with zero side effects (concrete spy
   test):** monkeypatch the module globals `headless.CertManager` and
   `headless.SessionTable` with **spy classes whose `__init__` raises**
   `AssertionError("must not construct on bad profile")`. Then
   `asyncio.run(serve(profile="does-not-exist", port=<free>, show_qr=False))` and
   assert it **returns `2`** and **neither spy was ever constructed** (no
   exception escaped → they were not touched; the cert was not generated, no
   token minted, no socket opened). This proves validation precedes cert
   generation, token minting, and socket setup — not merely that a return code
   came back. (A positive control — a valid profile name *does* reach the
   collaborators — is left to the live test in §B/`_live`, which exercises the
   real construction path; the unit test only needs the negative ordering proof,
   which is what would silently regress.)

**B. Launcher routing (the actual entry point — addresses concern that the unit
test could pass while `aitask_monitor.sh` still probes Textual / mishandles
forwarding):** skip if `websockets`/`msgpack`/`segno`/`pyyaml`/`tmux` missing.
- Run `bash .aitask-scripts/aitask_monitor.sh --headless-for-applink --help`.
- Assert exit 0, and stdout contains `--port`, `--profile`, **and** `--no-qr`
  (headless-specific flags) — proving the launcher routed to `headless.py` and
  forwarded the args.
- Assert stdout does **NOT** contain the normal-monitor help markers (e.g.
  `tmux session name` / `--interval`) — proving it did **not** fall through to
  the Textual `monitor_app.py`, i.e. Textual startup was skipped.

### `tests/test_applink_headless_live.sh` (NEW — live wss round-trip, skip-capable)

Addresses the task's explicit acceptance ("starts without a TTY; a scripted
client pairs and receives keyframes"). Runs the real path **in this task** when
deps allow; skips cleanly in dep-less CI. Skip if
`websockets`/`msgpack`/`segno`/`pyyaml`/`tmux`/`openssl` missing.

- **Pick a free port** (bind `127.0.0.1:0`, read the port, close) → pass as
  `--port`, avoiding collision with a real `:8765` applink.
- **Launch headless under no controlling TTY:** `setsid bash
  .aitask-scripts/aitask_monitor.sh --headless-for-applink --port <P>
  >"$log" 2>&1 &` (background); poll `$log` until the `Pair URL:` line appears
  (timeout ~15 s → FAIL). Parse the `applink://…?t=<token>&fp=<fp>` line for the
  token + fingerprint. This alone proves "starts without a TTY and serves a
  pairing endpoint."
- **Scripted `wss://` client (inline Python, `websockets` + `ssl`):** connect to
  `wss://127.0.0.1:<P>/`; pin the cert by comparing the peer cert's SHA-256
  base64url fingerprint against the printed `fp` (the same pinning the mobile
  client does). Send `pair` with the token → assert a `res` frame carrying a
  `bearer` and the `monitor_control` profile.
- **Keyframe (best-effort, read-only):** create a throwaway tmux session **in
  the repo cwd** (so discovery picks it up as an aitasks session) with one pane;
  over the paired bearer, `subscribe` to that pane's id → assert a **binary**
  keyframe frame arrives (first byte `0x01`) within a couple ticks. `subscribe`
  + capture are read-only (no keystrokes sent), so a developer's real `aitasks`
  session is never written to. If session creation/discovery is unavailable,
  emit a `SKIP: keyframe (no throwaway session)` and still pass the pair
  assertions.
- **Teardown (always, via `trap`):** kill only the throwaway tmux session we
  created; `kill -TERM` the headless pid and wait; assert it exited (clean
  `SIGTERM` shutdown). Optionally `kill -HUP` before `-TERM` and assert a second
  `Pair URL:` (fresh token) appears in `$log` — exercising the headless
  re-pairing affordance.

A **manual-verification follow-up** (offered at Step 8c) remains for the part no
automated test can cover here: pairing from the **real** mobile app
(`../aitasks_mobile`, cross-repo) and on-device keyframe rendering.

## Files to modify

### `.aitask-scripts/aitask_monitor.sh` — flag parsing, dep probe, routing, help

Currently it probes `textual`/`pyyaml` then `exec`s `monitor/monitor_app.py "$@"`.
`monitor_app.py` uses `argparse` (it would reject `--headless-for-applink`), so
the flag MUST be intercepted in the launcher **before** exec. Add, after the
`require_ait_python` line and before the existing Textual probe:

```bash
# Applink headless mode: skip the Textual monitor TUI and run the applink
# listener (control plane + push loop) with no terminal UI. The flag is parsed
# here because monitor_app.py's argparse does not know it.
headless=0
fwd=()
for a in "$@"; do
    if [[ "$a" == "--headless-for-applink" ]]; then
        headless=1
    else
        fwd+=("$a")
    fi
done

if [[ "$headless" -eq 1 ]]; then
    # Headless applink needs the applink deps (NOT textual — we skip the TUI).
    missing=()
    "$PYTHON" -c "import websockets" 2>/dev/null || missing+=(websockets)
    "$PYTHON" -c "import msgpack"    2>/dev/null || missing+=(msgpack)
    "$PYTHON" -c "import segno"      2>/dev/null || missing+=(segno)
    "$PYTHON" -c "import yaml"       2>/dev/null || missing+=(pyyaml)
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
    fi
    if ! command -v tmux &>/dev/null; then
        echo "Error: tmux is not installed. The applink bridge requires tmux." >&2
        exit 1
    fi
    exec "$PYTHON" "$SCRIPT_DIR/applink/headless.py" ${fwd[@]+"${fwd[@]}"}
fi
```

Notes:
- `${fwd[@]+"${fwd[@]}"}` is the bash-3.2-safe empty-array expansion (macOS) per
  `shell_conventions.md`.
- The headless branch does **not** call `ait_warn_if_incapable_terminal` (no TTY
  expected) — it runs before that line; the normal path is unchanged.
- **Help text:** discoverability is handled at two levels (see the
  `monitor_app.py` edit below for the user-visible `ait monitor --help` entry):
  `headless.py`'s own `argparse` owns the detailed `--help` for the headless mode
  (`ait monitor --headless-for-applink --help` forwards through to it), and a
  one-line mention is added to the launcher's top comment for anyone reading the
  script. We never intercept `--help` at the bash layer (so the normal TUI help
  path is untouched).

### `.aitask-scripts/monitor/monitor_app.py` — surface the flag in `ait monitor --help`

So that `ait monitor --help` (which the launcher forwards to `monitor_app.py`'s
`argparse`) actually **lists** the headless flag, register it in the parser
(`main()`, alongside `--session`/`--interval`/`--lines`):

```python
parser.add_argument(
    "--headless-for-applink", action="store_true",
    help="Run the applink bridge headless (no TUI), serving only the mobile "
         "listener. See 'ait monitor --headless-for-applink --help' for options.",
)
```

The launcher intercepts this flag before exec, so `monitor_app.py` never runs the
TUI in headless mode in normal use. Add a **defensive guard** at the top of
`main()` for the direct-invocation edge case (someone runs `python
monitor_app.py --headless-for-applink`, bypassing the launcher's dep-probe and
routing): if `args.headless_for_applink` is set, print a one-line pointer to
stderr ("Run this via the launcher: ait monitor --headless-for-applink") and
`return` (non-zero exit) instead of starting the Textual app. This keeps the
flag visible in help, keeps the launcher the single real router, and fails
clearly if the runner is bypassed. Additive, behavior-preserving for every
existing invocation.

### `.aitask-scripts/applink/server.py` — host the two shared defaults

`server.py` already defines `DEFAULT_HOST`/`DEFAULT_SESSION` and is Textual-free
— the natural single home for the port/profile defaults too. Add:

```python
DEFAULT_PORT = 8765
DEFAULT_PAIR_PROFILE = "monitor_control"
```

**Complete the dedupe at the consumer too:** `AppLinkServer.__init__` currently
hardcodes `pair_profile: str = "monitor_control"`. Change that default to
`pair_profile: str = DEFAULT_PAIR_PROFILE` so there is exactly **one** literal
for the pairing profile across the package (the constructor, the TUI, and the
headless runner all reference the same name). Same value → behavior-identical.

### `.aitask-scripts/applink/applink_app.py` — consume the shared defaults (dedupe)

Replace the local literals `DEFAULT_PORT = 8765` and `DEFAULT_PROFILE =
"monitor_control"` with an import from `server` so the TUI and the headless
runner share one source of truth (derive-don't-duplicate):

```python
from server import AppLinkServer, DEFAULT_PORT, DEFAULT_PAIR_PROFILE as DEFAULT_PROFILE
```

Behavior-identical (same values); the alias keeps the existing
`DEFAULT_PROFILE` name used by `AppLinkRuntime`. This is the only edit to the
live TUI and it is a pure constant re-home (no logic change).

### `website/content/docs/tuis/applink/how-to.md` — document headless mode

Add a "Run the bridge headless (unattended box)" section documenting:
`ait monitor --headless-for-applink [--port N] [--profile <name>] [--no-qr]`;
that it prints the pairing URL + fingerprint + ASCII QR to stdout; that
`SIGHUP` reprints a fresh pairing token and `SIGINT`/`SIGTERM` stop it cleanly;
that paired devices persist across restarts. Per project doc conventions, write
current-state only (no version history) and do **not** add this mode to any
TUI list — it is deliberately not a TUI (no `KNOWN_TUIS` entry, not switchable).

## Trade-offs & rejected alternatives

- **New `headless.py` vs a `--headless` mode inside `applink_app.py`:** chose the
  separate module — `applink_app.py` imports Textual at module top, so any entry
  routed through it cannot "skip Textual startup". A standalone runner is the
  only way to honor the task's no-Textual requirement. Cost: a small amount of
  setup logic mirrored from `AppLinkRuntime` (session table / cert / gate /
  token), which is inherent, not duplication of behavior.
- **Flag on `aitask_monitor.sh` vs `aitask_applink.sh`:** the task AC and the
  design-doc bullet both name `aitask_monitor.sh`; honored. The runner itself
  still lives in the `applink/` package (it is applink functionality); the
  monitor launcher only routes to it.
- **Print QR/URL vs require a pre-provisioned session:** chose print-to-stdout —
  it makes an unattended box actually pairable (scan the logged QR / copy the
  URL) with zero extra provisioning, and `SIGHUP` gives a no-TTY "regenerate"
  without restart. The pre-provisioned-session alternative shifts work onto the
  operator for no benefit here.
- **Sharing `DEFAULT_PORT`/`DEFAULT_PROFILE` via `server.py` vs redeclaring in
  `headless.py`:** chose the shared home to avoid a silent drift between the TUI
  default port and the headless default port; the guard is structural (one
  definition site).

## Verification

1. `shellcheck .aitask-scripts/aitask_monitor.sh` → clean.
2. `bash tests/test_applink_headless.sh` → PASS (no-Textual contract, pure
   render, `headless.py --help`, profile-name rejection, **and the launcher
   routing assertions: `ait monitor --headless-for-applink --help` forwards
   `--port`/`--profile`/`--no-qr` and does not fall through to the Textual TUI**).
3. `bash tests/test_applink_headless_live.sh` → PASS or SKIP (real `wss://`
   no-TTY launch → pair round-trip with fingerprint pinning → best-effort
   keyframe over a throwaway session → clean `SIGTERM` shutdown). Run during this
   task on a box with deps + tmux + openssl.
4. `bash tests/test_applink_smoke.sh && bash tests/test_applink_router.sh &&
   bash tests/test_applink_pairing.sh` → still PASS (no regressions from the
   `applink_app.py` / `server.py` constant re-home).
5. `python -c "import applink.headless"` (ait venv, `.aitask-scripts` on path) →
   no import error; `'textual' not in sys.modules`.
6. `ait monitor` (normal path) still launches the Textual TUI unchanged;
   `ait monitor --help` now **lists** `--headless-for-applink`.
7. **Real mobile client (manual — `../aitasks_mobile` is cross-repo/unavailable
   here):** pairing from the on-device app + on-device keyframe rendering →
   covered by the Step 8c manual-verification follow-up.

## Risk

### Code-health risk: low
- New routing branch in `aitask_monitor.sh`, a load-bearing launcher used by the
  desktop monitor TUI. A bug in the flag parse could affect the normal path.
  · severity: low · → mitigation: inline — the branch only fires on an exact
  `--headless-for-applink` token and forwards the remaining args unchanged; the
  normal path's probe/exec is untouched; `shellcheck` + the existing
  `test_applink_smoke`/regression suite cover it.
- The one edit to the live TUI (`applink_app.py`) is a pure constant re-home
  (same values, imported instead of literal). · severity: low · → mitigation:
  inline — covered by `test_applink_smoke.sh` (constructs the app) + the
  router/pairing tests.
- New module is isolated in the `applink/` package and Textual-free by an
  explicit asserted contract. · severity: low

### Goal-achievement risk: medium
- The **real mobile client is cross-repo/unavailable**, so on-device pairing and
  keyframe rendering cannot be automated here. · severity: medium · →
  mitigation: the live `wss://` path (no-TTY launch, fingerprint-pinned pair
  round-trip, best-effort keyframe over a throwaway session, clean shutdown) is
  now exercised **in this task** by `test_applink_headless_live.sh` (skip-capable
  in dep-less CI), and the launcher routing is exercised by the §B group of
  `test_applink_headless.sh` — so the synthetic acceptance the task names runs
  here, not only in a follow-up. The Step 8c manual-verification follow-up covers
  only the genuinely-cross-repo remainder (the real phone app).
- POSIX-only signal handling (`add_signal_handler`, `SIGHUP`/`SIGINT`/`SIGTERM`)
  — fine for the Linux/macOS bridge target; would not work on Windows, which is
  out of scope for `ait` TUIs/tmux. · severity: low · → mitigation: inline
  (documented; tmux dependency already constrains the platform).

## Step 9 (Post-Implementation)

Profile `fast`, current branch (no worktree). Code (`headless.py`,
`aitask_monitor.sh`, `server.py`, `applink_app.py`, `tests/…`, website doc) via
plain `git`; the plan via `./ait git`. Push via `./ait git push`. Archive this
child via `./.aitask-scripts/aitask_archive.sh 822_13` — parent t822 keeps
t822_14 pending. Sibling note for **t822_14** (push-scheduler resilience): the
headless runner is now a second long-lived host for `AppLinkServer` +
per-connection `PushScheduler` with no Textual event loop babysitting it — any
scheduler-resilience work must hold under this headless host too.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned.
  - `applink/headless.py` (NEW): the Textual-free runner. `render_pairing_block`
    (pure stdout builder, ASCII QR via `segno.make(uri).terminal(buf, border=1)`),
    `serve()` (profile-validate-first → cert/fingerprint → mint token → start
    `AppLinkServer` → print pairing block → SIGINT/SIGTERM stop, SIGHUP re-mint +
    reprint), `main()`/argparse with `--port`/`--profile`/`--no-qr`.
  - `aitask_monitor.sh`: parse `--headless-for-applink`, applink dep-probe
    (websockets/msgpack/segno/pyyaml — NOT textual), `exec` `applink/headless.py`
    with bash-3.2-safe `${fwd[@]+"${fwd[@]}"}` forwarding; normal TUI path
    untouched.
  - `monitor_app.py`: registered the flag in argparse so `ait monitor --help`
    lists it + a defensive guard (direct `python monitor_app.py
    --headless-for-applink` prints a launcher pointer and exits 2).
  - `server.py`: `DEFAULT_PORT`/`DEFAULT_PAIR_PROFILE` constants; constructor
    default now `pair_profile=DEFAULT_PAIR_PROFILE`. `applink_app.py`: imports
    both from `server` (dedupe, alias keeps `DEFAULT_PROFILE`).
  - Docs: headless section in `website/content/docs/tuis/applink/how-to.md`.
  - Tests: `tests/test_applink_headless.sh` (no-Textual import contract, render
    purity, `--help`, bad-profile **spy** ordering, launcher routing) and
    `tests/test_applink_headless_live.sh` (no-TTY `setsid` launch → cert-pinned
    `wss://` pair → real keyframe → SIGHUP reprint → clean SIGTERM).
- **Deviations from plan:** None of substance. The live test exceeded the
  plan's "best-effort keyframe" — on this box it created a throwaway repo-cwd
  tmux session that discovery picked up, so a real `0x01` keyframe was received
  and asserted (still SKIP-capable if no session/keyframe is available).
- **Issues encountered:** None. All collaborators were already Textual-free, so
  the runner assembled cleanly; the spy test confirmed validation precedes any
  `CertManager`/`SessionTable` construction.
- **Key decisions:** Separate `headless.py` (never import `applink_app`/
  `qr_widget`, both Textual) is the only way to honor "skip Textual startup".
  Profile validation runs before any side effect (token mint / cert gen /
  socket). Pairing-profile/port defaults centralized in `server.py` (Textual-free
  single source). Pairing in headless mode = print URL+fingerprint+ASCII QR;
  SIGHUP = no-TTY "regenerate" (rotates only the unused token, preserves the
  t822_2 stable-connection-ID invariant).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t822_14 (push-scheduler resilience):** `headless.py` is a second
    long-lived host for `AppLinkServer` + per-connection `PushScheduler` with no
    Textual event loop — resilience work must hold here too. The runner installs
    SIGINT/SIGTERM→stop and SIGHUP→reprint via `loop.add_signal_handler`; a
    scheduler that needs its own signal/lifecycle hooks should compose with
    these, not assume a Textual worker context.
  - **Verification harness reuse:** `tests/test_applink_headless_live.sh` shows
    a safe pattern for driving the real `wss://` server in a test — free port,
    cert-pinned client, throwaway repo-cwd tmux session for discovery, signal
    teardown. Reuse it for any future end-to-end applink server test.
  - **Real mobile client (`../aitasks_mobile`, cross-repo):** on-device pairing
    + keyframe rendering against the headless bridge is the Step 8c
    manual-verification follow-up — same wire contract as the TUI server (no
    protocol change; headless only changes the host process).
