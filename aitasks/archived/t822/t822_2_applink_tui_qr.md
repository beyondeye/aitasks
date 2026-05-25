---
priority: high
effort: medium
depends: [t822_1]
issue_type: feature
status: Done
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-24 09:31
updated_at: 2026-05-25 18:03
completed_at: 2026-05-25 18:03
---

Create the bare-bones `ait applink` Textual TUI and a working QR-pairing screen. No transport wiring yet — this child delivers the TUI skeleton, dispatcher wiring, dependency declaration, and a QR pairing screen that consumes the token shape defined in t822_1.

## Context

Parent task **t822** introduces `ait applink`. This is the first child that ships code. It produces a runnable `ait applink` that opens the Textual TUI, generates a pairing token per t822_1's spec, renders it as a QR code on screen, and displays a placeholder "no client connected" status. Socket wiring is *not* in scope (it's a follow-up that t822_3's design doc will scope out).

Pre-plan decisions locked:
- Module dir: `.aitask-scripts/applink/`
- QR library: **`segno`** (pure Python, no compiled deps; has a `terminal()` renderer that fits Textual `Static`)
- Mimic the most recent TUI (`brainstorm`) for app boilerplate, NOT older TUIs (board/monitor)

## Depends on

- t822_1 (needs the pairing-token shape and `applink://...?t=...&fp=...` URI form locked first)

## Key Files to Create

- `.aitask-scripts/applink/__init__.py`
- `.aitask-scripts/applink/applink_app.py` — Textual App (mimic `.aitask-scripts/brainstorm/brainstorm_app.py:~2110` `class BrainstormApp(TuiSwitcherMixin, App)` boilerplate; include `BINDINGS` and `TuiSwitcherMixin` so `j` switches across TUIs)
- `.aitask-scripts/applink/pairing.py` — module that generates the one-time pairing token + builds the QR URI from t822_1's spec
- `.aitask-scripts/aitask_applink.sh` — bash launcher (mimic `.aitask-scripts/aitask_brainstorm_tui.sh` lines 1-32)
- `website/content/docs/tuis/applink/_index.md`
- `website/content/docs/tuis/applink/how-to.md`
- `website/content/docs/tuis/applink/reference.md`

## Key Files to Modify

- `/home/ddt/Work/aitasks/ait` — add `applink) shift; exec "$SCRIPTS_DIR/aitask_applink.sh" "$@" ;;` to case statement near line 187; add help line near line 31
- `.aitask-scripts/lib/tui_registry.py` (lines 17-27 `TUI_REGISTRY`) — append `("applink", "App Linker", "ait applink", True)`
- `.aitask-scripts/aitask_setup.sh` — add `segno` to both `pip install` lines (lines 574 and 655), alongside existing `textual>=8.1.1,<9` and `pyyaml==6.0.3`
- `website/content/docs/tuis/_index.md` (line 23) — add `applink` to Available TUIs list

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py` — Textual App boilerplate (most recent TUI; gold reference)
- `.aitask-scripts/aitask_brainstorm_tui.sh` — launcher pattern (`require_ait_python_fast` from `lib/python_resolve.sh:133-145`, dep-check block, exec Python app)
- `website/content/docs/tuis/board/` — doc structure to mirror (_index.md, how-to.md, reference.md)
- `aidocs/tui_conventions.md` — TUI authoring conventions (read fully)
- `aidocs/python_tui_performance.md` — read if considering PyPy vs CPython (default is the same as brainstorm)
- `aidocs/applink/protocol.md` (produced by t822_1) — pairing URI spec

## Implementation Plan

1. **Confirm the token URI shape with t822_1's `aidocs/applink/protocol.md`** before writing `pairing.py`. If t822_1 is unlanded, block on it.
2. **Module scaffold:** `.aitask-scripts/applink/__init__.py` (empty), `pairing.py` (token gen + URI build), `applink_app.py` (Textual app with 2 screens: Pairing and Status).
3. **Pairing screen:**
   - Generate 256-bit token via `secrets.token_urlsafe(32)`
   - Detect first non-loopback LAN IPv4 (small helper; document fallback to `0.0.0.0` if none found)
   - Build URI per t822_1 spec
   - Render via `segno.make(uri).terminal(compact=True)` into a Textual `Static` widget
   - Footer: keybindings (`r` regenerate, `q` quit, `j` switch TUI)
   - Show the encoded URI below the QR in a dim color (debugging aid)
4. **Status screen:** placeholder card "No client connected" — switch via `s`. Leaves the socket-server hook as a TODO with a clear deferral comment pointing to a follow-up task.
5. **Launcher `aitask_applink.sh`:**
   - `#!/usr/bin/env bash` + `set -euo pipefail`
   - Source `lib/python_resolve.sh`, call `require_ait_python_fast`
   - Dep-check for `textual`, `segno` (fail with `ait setup` hint)
   - Exec `python -m applink.applink_app "$@"` (or direct path — match brainstorm)
6. **Dispatcher + registry + dep wiring:** as listed above.
7. **Website docs:** copy structure of `website/content/docs/tuis/board/` and tailor for applink (overview, screens, keybindings, future direction pointing to t822_3).
8. **Smoke entrypoint:** add `--smoke` flag to `applink_app.py` that constructs the app, renders one frame headlessly via `App.run_test()`, and exits 0. Wire a single line into `tests/test_*.sh` style or add `tests/test_applink_smoke.sh` (mimic existing test scaffolding).

## Verification Steps

- `ait applink` launches the TUI without errors
- The pairing screen renders a scannable QR code (open it in a phone QR app — should yield a valid `applink://...?t=...&fp=...` URI matching t822_1's grammar)
- `r` regenerates token (visibly different QR)
- `j` switches to another TUI (e.g. brainstorm) and back — proves `TuiSwitcherMixin` works
- `q` quits cleanly
- `python -m applink.applink_app --smoke` exits 0
- `bash tests/test_applink_smoke.sh` passes
- `ait setup` on a fresh machine installs `segno` without errors
- `shellcheck .aitask-scripts/aitask_applink.sh` passes
- `cd website && ./serve.sh` shows the new applink pages under TUIs

## Out of Scope

- Actual WebSocket/transport listener (deferred to a follow-up task scoped by t822_3)
- Receiving and processing real client commands (deferred)
- TLS certificate generation/management (mentioned as TODO in `pairing.py`)
- Mobile-side scanning UI (lives in `../aitasks_mobile`)
