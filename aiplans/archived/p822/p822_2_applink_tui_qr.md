---
Task: t822_2_applink_tui_qr.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_3_monitor_port_design.md, aitasks/t822/t822_4_manual_verification_new_ait_bridge_tui.md, aitasks/t822/t822_5_applink_qr_add_hostname_field.md
Archived Sibling Plans: aiplans/archived/p822/p822_1_applink_protocol_design.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 17:28
---

# Plan: t822_2 — applink TUI skeleton + QR pairing screen

## Context

Second child of parent t822 introducing `ait applink`. First task that ships code. Builds on t822_1 (now archived) which landed `aidocs/applink/protocol.md` with the pairing URI grammar locked. Delivers a runnable `ait applink` TUI that opens, generates a token, renders a QR code, and exits cleanly — no socket wiring yet (deferred to a follow-up scoped by sibling t822_3).

## Verification status (verify path, 2026-05-25)

Re-verified plan against current codebase under profile `fast`. Adjustments applied below:
- **QR library:** keep `segno` (the original task's pre-plan pick) — chosen specifically because it supports **Micro QR codes** (smaller QR variant for short payloads), which `qrcode` (lincolnloop) does not. Even though the v1 pairing URI is too long for Micro QR, the capability is retained for future short-data screens (e.g. fingerprint-only verification). We do NOT use `segno`'s built-in `.terminal()` renderer — instead we build a custom Textual `Static` subclass that walks `qr.matrix` and emits half-block chars for maximally compact rendering.
- **Launcher function:** `require_ait_python_fast` does NOT exist — the correct helper is `require_ait_python()` in `.aitask-scripts/lib/python_resolve.sh:87-89`. Plan updated.
- **Setup pip install:** Single unified line `.aitask-scripts/aitask_setup.sh:519` (not split at 574/655 as plan originally cited). Plan updated.
- **ait dispatcher line numbers:** Case statement now at lines 173-292; help block at lines 20-87 with "TUI:" section at lines 24-32; existing TUI dispatch entries at lines 180-189. Plan updated.
- **TUI registry:** `TUI_REGISTRY` lives at `.aitask-scripts/lib/tui_registry.py:17-27` (verified). `KNOWN_TUIS` in `tui_switcher.py` is derived from `switcher_tuis()` — no manual edit needed there.
- **URI grammar:** `aidocs/applink/protocol.md:96-98` defines `applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>&name=<urlencoded(hostname)>`. The `&name=` field is optional but in spec; include it (helps the mobile UI label devices).
- **Website TUI list:** Lives at `website/content/docs/tuis/_index.md:14-24` (section "## Available TUIs"). Insert `applink` alphabetically.

## Pre-flight check

1. Confirm `aidocs/applink/protocol.md` has the `## Pairing flow` section (lines 89-122). ✓ Verified.
2. Read `aidocs/tui_conventions.md` (full).
3. Skim `.aitask-scripts/brainstorm/brainstorm_app.py:2110-2200` for `class BrainstormApp(TuiSwitcherMixin, App)` boilerplate; BINDINGS list at lines 2742-2764 starts with `*TuiSwitcherMixin.SWITCHER_BINDINGS`.
4. Skim `.aitask-scripts/aitask_brainstorm_tui.sh` (lines 1-33) for the launcher pattern.
5. Skim `.aitask-scripts/codebrowser/codebrowser_app.py:1-50` for a smaller App import-header reference (mirror its `sys.path.insert(...)` + `from tui_switcher import TuiSwitcherMixin` shape).

## Files to create

1. **`.aitask-scripts/applink/__init__.py`** — empty.

2. **`.aitask-scripts/applink/pairing.py`** — pure functions:
   - `generate_token() -> str` — 256-bit, via `secrets.token_urlsafe(32)`.
   - `detect_lan_ip() -> str` — try `socket.getaddrinfo(socket.gethostname(), None)` and filter out loopback IPv4; fall back to `0.0.0.0` if none found. Document the fallback in a docstring.
   - `build_pairing_uri(token: str, ip: str, port: int, fingerprint: str, hostname: str | None = None) -> str` — emits `applink://<ip>:<port>/pair?t=<token>&fp=<fp>` with optional `&name=<urlencoded(hostname)>` per `aidocs/applink/protocol.md:96-98`.
   - `compute_self_signed_fingerprint() -> str` — TODO stub returning `"NOT-IMPLEMENTED"` with a code comment pointing to the deferred follow-up. Keep the seam so swapping in a real implementation later is one function replacement.

3. **`.aitask-scripts/applink/qr_widget.py`** — `class TerminalQR(Static)`: takes `data: str`, renders an offline QR code as compact text using `segno` and half-block characters. `segno`'s built-in `.terminal()` is intentionally bypassed — walking `qr.matrix` directly gives us full control over cell width and lets the same widget render Micro QR symbols later. Algorithm:

   ```python
   import segno
   from textual.widgets import Static

   class TerminalQR(Static):
       """Static widget that renders a QR (or Micro QR) code as compact half-block text."""

       # Each cell is rendered as TWO characters wide because terminal cells are
       # roughly 2:1 tall:wide — doubling the width keeps the QR roughly square.
       BLOCK_MAP = {
           (0, 0): "  ",   # both light
           (1, 0): "▀▀",   # top dark
           (0, 1): "▄▄",   # bottom dark
           (1, 1): "██",   # both dark
       }

       def __init__(self, data: str, *, micro: bool | None = None, border: int = 2, **kwargs):
           super().__init__(**kwargs)
           self._border = border
           self._micro = micro     # None = auto, True = force micro, False = standard
           self._data = data
           self._refresh_qr()

       def set_data(self, data: str) -> None:
           self._data = data
           self._refresh_qr()

       def _refresh_qr(self) -> None:
           # micro=None → segno auto-picks Micro if data fits, else standard QR.
           qr = segno.make(self._data, micro=self._micro)
           # qr.matrix is a tuple of bytearrays (rows of 0/1 ints).
           rows = [list(row) for row in qr.matrix]
           b = self._border
           width = len(rows[0]) + 2 * b
           # Pad with quiet zone (border rows top/bottom and columns left/right).
           pad_row = [0] * width
           padded = [pad_row[:] for _ in range(b)]
           for row in rows:
               padded.append([0] * b + row + [0] * b)
           padded.extend([pad_row[:] for _ in range(b)])
           # Pad to even row count so pairing always succeeds.
           if len(padded) % 2:
               padded.append(pad_row[:])
           lines = []
           for top, bottom in zip(padded[0::2], padded[1::2]):
               lines.append("".join(self.BLOCK_MAP[(t, bot)] for t, bot in zip(top, bottom)))
           self.update("\n".join(lines))
   ```

   Each pair of QR rows collapses into one terminal row using ▀ (top), ▄ (bottom), █ (both), or space (neither). The `(2 chars wide × half-block tall)` cell roughly matches standard terminal cell aspect ratio (~2:1), keeping the rendered QR square. `micro=None` lets `segno` auto-select Micro vs. standard based on payload length — the pairing URI is too long for Micro today, but the widget is forward-compatible.

4. **`.aitask-scripts/applink/applink_app.py`** — Textual App. Mirror codebrowser_app.py header pattern:

   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
   from tui_switcher import TuiSwitcherMixin
   ```

   - `class ApplinkApp(TuiSwitcherMixin, App)` with:
     ```python
     BINDINGS = [
         *TuiSwitcherMixin.SWITCHER_BINDINGS,
         Binding("q", "quit", "Quit"),
         Binding("r", "regenerate", "Regenerate token"),
         Binding("s", "show_status", "Status screen"),
         Binding("p", "show_pairing", "Pairing screen"),
     ]
     ```
   - Two `Screen`s: `PairingScreen`, `StatusScreen` managed via `App.push_screen` / `pop_screen`.
   - `PairingScreen`: header "Pair a device", a `TerminalQR` widget (above), a `Static` showing the raw URI in `dim` style for debugging, footer. `action_regenerate` calls `TerminalQR.set_data(new_uri)` after regenerating the token.
   - `StatusScreen`: placeholder `Static("No client connected — socket wiring is a follow-up task")`.
   - `--smoke` CLI flag (argparse): construct the app and exit 0 without entering the event loop (call `App()` constructor, render one frame via `App.run_test()` if needed, else just import and exit). Used by CI smoke test.

5. **`.aitask-scripts/aitask_applink.sh`** — bash launcher. Mirror `aitask_brainstorm_tui.sh`:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   # shellcheck source=lib/aitask_path.sh
   source "$SCRIPT_DIR/lib/aitask_path.sh"
   # shellcheck source=lib/python_resolve.sh
   source "$SCRIPT_DIR/lib/python_resolve.sh"
   # shellcheck source=lib/terminal_compat.sh
   source "$SCRIPT_DIR/lib/terminal_compat.sh"

   PYTHON="$(require_ait_python)"

   missing=()
   "$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
   "$PYTHON" -c "import segno"   2>/dev/null || missing+=(segno)
   if [[ ${#missing[@]} -gt 0 ]]; then
       die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
   fi

   ait_warn_if_incapable_terminal

   if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
       echo "Usage: ait applink"
       echo ""
       echo "Launch the App Linker TUI for pairing a mobile companion."
       exit 0
   fi

   exec "$PYTHON" "$SCRIPT_DIR/applink/applink_app.py" "$@"
   ```

6. **`tests/test_applink_smoke.sh`** — minimal bash test mirroring existing scaffolding. Invokes the smoke entry (`python applink_app.py --smoke`), asserts exit 0 and no stderr.

7. **`website/content/docs/tuis/applink/_index.md`** — overview page (mirror `website/content/docs/tuis/board/_index.md`).

8. **`website/content/docs/tuis/applink/how-to.md`** — pairing walkthrough.

9. **`website/content/docs/tuis/applink/reference.md`** — keybindings, screens, env vars.

## Files to modify

- **`/home/ddt/Work/aitasks/ait`**
  - Add a dispatch line in the case block (lines 180-189 area; alphabetical near `board)`):
    ```bash
    applink)      shift; exec "$SCRIPTS_DIR/aitask_applink.sh" "$@" ;;
    ```
  - Add a help-text line in the `TUI:` block (lines 24-32, alphabetical):
    ```
    applink        Launch the App Linker TUI (mobile pairing)
    ```

- **`.aitask-scripts/lib/tui_registry.py`** — append to `TUI_REGISTRY` (lines 17-27):
  ```python
  ("applink",     "App Linker",    "ait applink",     True),
  ```

- **`.aitask-scripts/aitask_setup.sh`** — extend the single pip install at line 519. Append `'segno>=1.5,<2'`:
  ```bash
  "$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3' 'minijinja>=2.0,<3' 'pexpect>=4.9,<5' 'segno>=1.5,<2'
  ```

- **`website/content/docs/tuis/_index.md`** — add `applink` to the "Available TUIs" list (lines 14-24), alphabetically.

## Reference files (read-only)

- `.aitask-scripts/brainstorm/brainstorm_app.py:2110+` — App boilerplate (gold reference; most recent TUI)
- `.aitask-scripts/codebrowser/codebrowser_app.py:1-50` — simpler import-header pattern
- `.aitask-scripts/aitask_brainstorm_tui.sh:1-33` — launcher pattern
- `.aitask-scripts/lib/python_resolve.sh:87-89` — `require_ait_python` (zero-arg)
- `.aitask-scripts/lib/tui_switcher.py:866-895` — `TuiSwitcherMixin`, `SWITCHER_BINDINGS`, `action_tui_switcher`
- `.aitask-scripts/lib/tui_registry.py` — `TUI_REGISTRY` (full file is 41 lines; read it)
- `aidocs/tui_conventions.md`
- `aidocs/applink/protocol.md` (from t822_1) — pairing URI spec at lines 89-122

## Verification

1. `bash tests/test_applink_smoke.sh` → PASS
2. `shellcheck .aitask-scripts/aitask_applink.sh` → no warnings
3. `./ait applink` opens the TUI without traceback
4. QR scans cleanly with a phone QR reader and yields a URI matching the `applink://<ip>:<port>/pair?t=<token>&fp=<fp>[&name=<host>]` grammar from `aidocs/applink/protocol.md`
5. `r` regenerates → visibly different QR
6. `s` switches to Status screen, `p` switches back to Pairing
7. `j` switches to another TUI (e.g. brainstorm) via the TuiSwitcherMixin and back
8. `q` quits cleanly (exit 0)
9. Fresh `ait setup` on a clean venv installs `segno` without errors
10. `cd website && ./serve.sh` shows the new applink pages under the TUIs nav

## Manual verification follow-up

This task produces TUI behavior only a human can fully validate (QR scan, switcher integration, regeneration). Parent t822 flagged it as a candidate for the aggregate manual-verification sibling created at parent-planning time (now living as t822_4).

## Out of scope

- WebSocket listener / handling of `pair` request frames (deferred — scoped by sibling t822_3)
- Real TLS cert / fingerprint generation (stubbed in `pairing.py` with a code comment)
- Connection state machine implementation (defined in `aidocs/applink/protocol.md` but not yet wired)
- Mobile-side scanning (lives in `../aitasks_mobile`)

## Step 9 (Post-Implementation)

Standard cleanup per task-workflow Step 9:
- Commit on current branch (profile `fast`, no worktree)
- Push via `./ait git push`
- Archive task and plan via `./.aitask-scripts/aitask_archive.sh 822_2`
- Parent t822 keeps `t822_3`, `t822_4`, `t822_5` pending — archival will only close this child

## Post-Review Changes

### Change Request 1 (2026-05-25)

- **Requested by user:** (a) Move `applink` in the switcher list so it appears **after** the Statistics TUI (not in alphabetical position). (b) Assign a single-letter keyboard shortcut like every other switcher-visible TUI. (c) Clarify how the regenerate action interacts with already-paired clients — stable connection IDs must survive a regenerate. (d) Stop showing the raw `applink://` URI in the final TUI; the QR alone is sufficient and the plaintext URI leaks the pairing token to bystanders.
- **Changes made:**
  - `.aitask-scripts/lib/tui_registry.py` — moved the `applink` entry to position 5 (after `stats`, before `diffviewer`).
  - `.aitask-scripts/lib/tui_switcher.py` — added `"applink": "a"` to `_TUI_SHORTCUTS`, added `Binding("a", "shortcut_applink", "App Linker", show=False)` to `BINDINGS`, and added `action_shortcut_applink()` calling `self._shortcut_switch("applink")`.
  - `.aitask-scripts/applink/applink_app.py` — removed the `Static(self._uri, id="pairing_uri")` widget and its CSS block; pruned the matching `query_one("#pairing_uri", …).update(...)` call inside `action_regenerate`; added a comment explaining the regenerate invariant.
  - `.aitask-scripts/applink/pairing.py` — expanded `generate_token()` docstring with the **Stable-connection-ID invariant**: regenerating only invalidates the unused pairing token; already-issued bearers (and their connection IDs) stay valid. The t822_3 follow-up that wires the WebSocket listener must preserve this invariant.
  - `website/content/docs/tuis/applink/_index.md`, `how-to.md`, `reference.md` — removed mentions of the raw URI display and documented the regenerate invariant.
- **Files affected:** `.aitask-scripts/lib/tui_registry.py`, `.aitask-scripts/lib/tui_switcher.py`, `.aitask-scripts/applink/applink_app.py`, `.aitask-scripts/applink/pairing.py`, `website/content/docs/tuis/applink/_index.md`, `website/content/docs/tuis/applink/how-to.md`, `website/content/docs/tuis/applink/reference.md`.

## Final Implementation Notes

- **Actual work done:**
  - Created `.aitask-scripts/applink/` package: `__init__.py`, `pairing.py` (token generation, LAN IP probe with UDP-connect fallback, URI builder, TLS fingerprint stub), `qr_widget.py` (`TerminalQR(Static)` — walks `segno.QRCode.matrix` directly and emits half-block Unicode for compact rendering; auto-selects Micro QR when payload fits), `applink_app.py` (`ApplinkApp(TuiSwitcherMixin, App)` with `PairingScreen` + `StatusScreen`, `--smoke` headless entry).
  - Created `.aitask-scripts/aitask_applink.sh` launcher mirroring `aitask_brainstorm_tui.sh` (sources `aitask_path.sh`, `python_resolve.sh`, `terminal_compat.sh`; dep-checks `textual` + `segno`; warns on incapable terminals; supports `--help`).
  - Wired `ait applink` dispatcher case in `ait` and added help-text line under the `TUI:` section.
  - Registered `applink` in `TUI_REGISTRY` (positioned after `stats` per user feedback) and added `a` shortcut wiring in `lib/tui_switcher.py` (`_TUI_SHORTCUTS`, `BINDINGS`, `action_shortcut_applink`).
  - Added `'segno>=1.5,<2'` to the unified pip install in `aitask_setup.sh:519`.
  - Added `tests/test_applink_smoke.sh` (boots `ApplinkApp` headlessly via `--smoke`).
  - Wrote three website pages under `website/content/docs/tuis/applink/` (`_index.md`, `how-to.md`, `reference.md`) and added an Available-TUIs entry pointing at them.
- **Deviations from plan:**
  - Plan originally placed `applink` alphabetically in `TUI_REGISTRY`; user review requested it after `stats`. Plan also did not specify a switcher shortcut letter — added during review.
  - Plan included a dim raw-URI `Static` below the QR for debugging; user requested it removed because it leaks the pairing token in plaintext. Done; the QR is now sufficient, and the `--smoke` test still exercises URI construction internally.
  - LAN IP detection added a second fallback (UDP-connect to 8.8.8.8 to read the kernel-selected source address) beyond what the plan called for, because `getaddrinfo(gethostname())` returns only loopback on some Linux setups.
- **Issues encountered:**
  - `require_ait_python_fast` (cited in the original task description) does not exist; the canonical helper is `require_ait_python()`. Caught during plan verification (verify path).
  - `segno` was not pre-installed in the ait venv; installed locally via `~/.aitask/venv/bin/pip install 'segno>=1.5,<2'` for smoke-testing. The `aitask_setup.sh` edit ensures fresh installs pick it up.
- **Key decisions:**
  - Kept `segno` over `qrcode` (user preference) specifically for Micro QR support — `qr_widget.TerminalQR` passes `micro=None` so segno auto-picks; the v1 pairing URI is too long for Micro but the widget is forward-compatible (future short-data screens like fingerprint-only verification).
  - Custom half-block widget instead of `segno.terminal()`: 2-char-wide cells give a square QR in standard terminal cell aspect ratio (~2:1).
  - Two-screen design (`PairingScreen`, `StatusScreen`) managed via `push_screen`/`pop_screen`, mirroring `codebrowser_app.py` rather than the larger `brainstorm_app.py`.
  - Stable-connection-ID invariant: regenerate only rotates the unused pairing token; bearers issued to already-paired clients (and their connection IDs) survive. Documented in `pairing.generate_token()` docstring and in the website docs so the t822_3 follow-up enforces it when implementing bearer issuance.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t822_3 (monitor port design / WebSocket listener):** When implementing the `pair` request handler, preserve the stable-connection-ID invariant — bearers issued before a regenerate must continue to validate. Swap `compute_self_signed_fingerprint()` (currently returns `"NOT-IMPLEMENTED"`) for the real TLS-cert fingerprint then; that single-function replacement is the only pairing-side change needed here.
  - **t822_4 (manual verification):** verification items now include the switcher shortcut (`j` then `a`) and confirming that the raw URI is NOT shown in the Pairing screen.
  - **t822_5 (hostname field in QR):** already wired — `build_pairing_uri()` accepts an optional `hostname` kwarg and emits `&name=<urlencoded(hostname)>`. The `ApplinkApp` passes `socket.gethostname()` automatically.
- **Manual-verification failure:** item "[t822_2] `shellcheck .aitask-scripts/aitask_applink.sh` reports no warnings" failed; follow-up task t1002.
