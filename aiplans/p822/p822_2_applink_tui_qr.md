---
Task: t822_2_applink_tui_qr.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_1_applink_protocol_design.md, aitasks/t822/t822_3_monitor_port_design.md
Archived Sibling Plans: aiplans/archived/p822/p822_*_*.md
Worktree: (current branch — profile fast)
Branch: (current branch — profile fast)
Base branch: main
---

# Plan: t822_2 — applink TUI skeleton + QR pairing screen

## Context

Second child of parent t822. First task that ships code. Depends on t822_1 having landed `aidocs/applink/protocol.md` with the pairing URI grammar locked. Delivers a runnable `ait applink` TUI that opens, generates a token, renders the QR, and exits cleanly — no socket wiring yet.

## Pre-flight check

1. Confirm `aidocs/applink/protocol.md` exists and has a `## Pairing flow` section defining the `applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>` URI shape. If not, BLOCK and pick t822_1 first.
2. Read `aidocs/tui_conventions.md` (full).
3. Skim `.aitask-scripts/brainstorm/brainstorm_app.py:2100-2200` for the App boilerplate (`class BrainstormApp(TuiSwitcherMixin, App)`, `BINDINGS`, switcher hook).
4. Skim `.aitask-scripts/aitask_brainstorm_tui.sh:1-32` for the launcher pattern.

## Files to create

1. **`.aitask-scripts/applink/__init__.py`** — empty.
2. **`.aitask-scripts/applink/pairing.py`** — pure functions:
   - `generate_token() -> str` (256-bit, `secrets.token_urlsafe(32)`)
   - `detect_lan_ip() -> str` (try `socket.getaddrinfo` + filter non-loopback IPv4; fallback to `0.0.0.0`)
   - `build_pairing_uri(token, ip, port, fingerprint) -> str` (per t822_1 grammar)
   - `compute_self_signed_fingerprint() -> str` — TODO stub returning `"NOT-IMPLEMENTED"` with a code comment pointing to the deferred follow-up task. Keep the seam so swapping in a real impl later is one-function-replacement.
3. **`.aitask-scripts/applink/applink_app.py`** — Textual App:
   - `class ApplinkApp(TuiSwitcherMixin, App)` with `BINDINGS = [("q","quit"), ("r","regenerate"), ("s","status"), ("p","pairing"), ("j","switch_tui")]`
   - Two `Screen`s: `PairingScreen`, `StatusScreen` (use `App.push_screen` / `pop_screen`)
   - `PairingScreen`: container with title "Pair a device", a `Static` showing `segno.make(uri).terminal(compact=True)`, a `Static` with the encoded URI in dim style, footer with keybindings. `action_regenerate` regenerates token + re-renders.
   - `StatusScreen`: placeholder `Static("No client connected — socket wiring is a follow-up task")`.
   - `--smoke` CLI flag (argparse): build the app, call `App.run_test()` for one frame, exit 0. Used by CI smoke test.
4. **`.aitask-scripts/aitask_applink.sh`** — bash launcher:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   # shellcheck source=lib/python_resolve.sh
   source "$SCRIPT_DIR/lib/python_resolve.sh"
   require_ait_python_fast
   python -c "import textual, segno" 2>/dev/null || {
     echo "Missing Python deps. Run: ait setup" >&2; exit 1; }
   exec python -m applink.applink_app "$@"
   ```
   (Confirm exact `require_ait_python_fast` invocation against `aitask_brainstorm_tui.sh`.)
5. **`tests/test_applink_smoke.sh`** — minimal bash test mirroring existing test scaffolding (assert_eq helpers), invokes `python -m applink.applink_app --smoke`, asserts exit 0 and no stderr.
6. **`website/content/docs/tuis/applink/_index.md`** — overview page (mirror `website/content/docs/tuis/board/_index.md`).
7. **`website/content/docs/tuis/applink/how-to.md`** — pairing walkthrough.
8. **`website/content/docs/tuis/applink/reference.md`** — keybindings, screens, env vars.

## Files to modify

- `/home/ddt/Work/aitasks/ait` — add `applink) shift; exec "$SCRIPTS_DIR/aitask_applink.sh" "$@" ;;` to the case statement near line 187; add help line `applink   - launch the App Linker TUI (mobile pairing)` near line 31. Verify exact line numbers before editing (the file is the dispatcher, large).
- `.aitask-scripts/lib/tui_registry.py` — append `("applink", "App Linker", "ait applink", True)` to `TUI_REGISTRY` (lines 17-27).
- `.aitask-scripts/aitask_setup.sh` — append `segno` to both `pip install` lines (around lines 574 and 655) alongside `textual>=8.1.1,<9` and `pyyaml==6.0.3`. Pin loosely: `segno>=1.5,<2`. Verify exact line numbers before editing.
- `website/content/docs/tuis/_index.md` (line 23) — add `applink` to the Available TUIs list.

## Reference files (read-only)

- `.aitask-scripts/brainstorm/brainstorm_app.py:~2110` — App boilerplate (gold reference; most recent TUI)
- `.aitask-scripts/aitask_brainstorm_tui.sh:1-32` — launcher pattern
- `.aitask-scripts/lib/python_resolve.sh:133-145` — `require_ait_python_fast`
- `.aitask-scripts/lib/tui_switcher.py` — `KNOWN_TUIS` / `TuiSwitcherMixin` (confirm class name; recently renamed from `KNOWN_TUIS` to `TUI_REGISTRY` per Explore findings — read the file fully)
- `aidocs/tui_conventions.md`
- `aidocs/python_tui_performance.md` — read if questioning CPython vs PyPy (stick with framework default)
- `aidocs/applink/protocol.md` (from t822_1) — pairing URI spec
- `website/content/docs/tuis/board/` — doc structure template

## Verification

End-to-end (manual + scripted):

1. `bash tests/test_applink_smoke.sh` → PASS
2. `shellcheck .aitask-scripts/aitask_applink.sh` → no warnings
3. `./ait applink` opens the TUI without traceback
4. QR scans cleanly with a phone QR reader and yields a URI matching the `applink://...?t=...&fp=...` grammar from `aidocs/applink/protocol.md`
5. `r` regenerates → visibly different QR
6. `s` switches to Status screen, `p` switches back to Pairing
7. `j` switches to brainstorm (or another TUI) and back — `TuiSwitcherMixin` works
8. `q` quits cleanly (exit 0)
9. Fresh `ait setup` on a clean venv installs `segno` without errors
10. `cd website && ./serve.sh` shows the new applink pages under TUIs nav

## Manual verification follow-up

This task produces TUI behavior only a human can fully validate (QR scan, switcher, regeneration). The parent t822 plan flags this as a candidate for the manual-verification sibling created at parent-planning time.

## Out of scope

- WebSocket listener / handling of `pair` request frames (deferred to a follow-up task scoped by t822_3)
- Real TLS cert / fingerprint generation (stubbed in `pairing.py` with a code comment)
- Connection state machine implementation (defined in `aidocs/applink/protocol.md` but not yet wired)
- Mobile-side scanning (lives in `../aitasks_mobile`)
