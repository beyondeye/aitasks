---
Task: t713_2_syncer_entrypoint_and_tui.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md, aitasks/t713/t713_7_manual_verification_syncer_tui.md
Archived Sibling Plans: aiplans/archived/p713/p713_1_desync_state_helper.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-29 23:53
---

# t713_2 — Syncer entrypoint and Textual TUI shell

## Context

Parent task **t713** introduces an `ait syncer` TUI for tracking remote desync
state on the project's `main` and `aitask-data` git refs. The motivating
incident was `aitask_changelog.sh --gather` silently skipping tasks whose
archive sat on `origin/aitask-data` but had not been pulled into the local
`.aitask-data/` worktree.

Sibling t713_1 has already shipped `.aitask-scripts/lib/desync_state.py` with a
stable `snapshot [--fetch] [--ref ...] [--format json|text|lines]` interface.

This child (t713_2) builds the **command entrypoint and the first usable
Textual TUI shell** on top of that helper. It deliberately does **not**:
- wire sync/pull/push actions (sibling **t713_3**),
- register the TUI in `tui_registry.py` / add a switcher shortcut / monitor
  integration / `tmux.syncer.autostart` (sibling **t713_4**),
- update `aitasks/metadata/project_config.yaml` defaults or the helper-script
  whitelist touchpoints (sibling **t713_5**),
- write user docs (sibling **t713_6**).

After this child, `ait syncer` opens, polls, and displays state for `main`
and `aitask-data`. Resolution actions and integrations come in subsequent
siblings.

## Verified assumptions (verify-path)

- `desync_state.py snapshot --fetch --json` exists and returns `{"refs": [...]}`
  with per-ref `name`, `worktree`, `local_ref`, `remote_ref`, `status`,
  `ahead`, `behind`, `remote_commits`, `remote_changed_paths`, `error`. Default
  ref set is exactly `["main", "aitask-data"]`. (Confirmed:
  `.aitask-scripts/lib/desync_state.py:156-159` and live JSON output.)
- Helper functions `require_ait_python` (in `lib/python_resolve.sh:87`) and
  `ait_warn_if_incapable_terminal` (in `lib/terminal_compat.sh:102`) exist
  and are used by `aitask_board.sh` / `aitask_codebrowser.sh`.
- `ait` dispatcher edits land in three known locations:
  - usage block, lines 24-31 (TUI section),
  - update-check skip list, line 167,
  - dispatcher case block, lines 171-188.
- `TuiSwitcherMixin` (`lib/tui_switcher.py:723-751`) provides the `j`
  switcher binding. Setting `self.current_tui_name = "syncer"` is fine even
  before t713_4 registers `"syncer"` in `TUI_REGISTRY` — the switcher's
  `_build_tui_list` simply won't list syncer until then; `j` from the
  syncer to other TUIs still works.
- Board's `LoadingOverlay` (`board/aitask_board.py:2977-2987`) is the canonical
  modal pattern for blocking-while-fetching affordances.

## Implementation steps

### 1. Update root `ait`

Three edits:
- **Usage** (after `settings`, before the closing `EOF`): add
  `  syncer         Launch the remote-desync syncer TUI`.
- **Update-check skip list** (line 167): add `syncer` to the
  `help|--help|...|ide)` `;;` arm so launching the TUI is not delayed by the
  GitHub release check.
- **Dispatcher** (alongside `board`/`codebrowser` cases): add
  `    syncer)       shift; exec "$SCRIPTS_DIR/aitask_syncer.sh" "$@" ;;`.

### 2. Create `.aitask-scripts/aitask_syncer.sh`

Mirror `aitask_codebrowser.sh` exactly (it's the smaller of the two TUI
wrappers and matches our needs — only `textual` and `yaml` deps required):

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
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

ait_warn_if_incapable_terminal

exec "$PYTHON" "$SCRIPT_DIR/syncer/syncer_app.py" "$@"
```

Make it executable (`chmod +x`).

### 3. Create `.aitask-scripts/syncer/syncer_app.py`

Module layout (single file is sufficient at this stage; a sibling can split
later if needed):

- `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))`
  so we can import `desync_state` and `tui_switcher`.
- `from desync_state import snapshot` — call the helper in-process for
  speed. It is pure Python with `subprocess` calls and no top-level side
  effects; importing is safe.
- `from tui_switcher import TuiSwitcherMixin`.

CLI:
- `--interval N` — polling interval in seconds (default `30`). This satisfies
  the parent's "configurable interval, default ~30s" requirement without
  needing the `project_config.yaml` plumbing that t713_5 will add.
- `--no-fetch` — debug flag: poll without `git fetch` (useful when offline).

App class `SyncerApp(TuiSwitcherMixin, App)`:

- `TITLE = "aitasks syncer"`
- `current_tui_name = "syncer"` (set in `__init__`).
- `BINDINGS`:
  - `*TuiSwitcherMixin.SWITCHER_BINDINGS` (gives `j` for switcher)
  - `Binding("q", "quit", "Quit")`
  - `Binding("r", "refresh", "Refresh now")`
  - `Binding("f", "toggle_fetch", "Fetch on/off")` *(toggles `--no-fetch`
    runtime — small affordance for debugging; harmless if removed)*

Layout (vertical split, keep simple — sibling t713_3 will add action affordances):

```
┌─ Header ─────────────────────────────────────────────────┐
│ DataTable (id="branches")                                │
│   Branch | Status | Ahead | Behind | Last refresh        │
│   main   | ok     |     2 |     0  | 12:34:56            │
│   aitask-data | ok|     0 |     0  | 12:34:56            │
├──────────────────────────────────────────────────────────┤
│ Static (id="detail") — selected-row detail               │
│   Worktree, error (if any), commit subjects, paths       │
└─ Footer (binding hints) ─────────────────────────────────┘
```

- Use `DataTable(cursor_type="row", zebra_stripes=True)` so left/right keys
  stay free for future use (per CLAUDE.md TUI conventions).
- `Static` detail pane in a `VerticalScroll` so long path lists stay
  scrollable.

Polling and rendering:

- `on_mount`:
  - `self._interval = self.cli_args.interval or 30`
  - `self._fetch = not self.cli_args.no_fetch`
  - Seed the table with the two row keys (`main`, `aitask-data`) and a
    "loading…" status; do not block mount.
  - Kick off the first refresh: `self.call_later(self.action_refresh)`.
  - `self._poll_timer = self.set_interval(self._interval, self.action_refresh)`.
- `action_refresh` is a `@work(thread=True, exclusive=True)` worker that:
  1. Calls `desync_state.snapshot(None, self._fetch)` — captures the dict.
  2. Pushes a `LoadingOverlay("Fetching…")` only when `self._fetch` is true and
     the call is taking visibly long; v1 can skip the overlay entirely (the
     fetch is fast in practice). Decision: **omit the overlay in v1**; the
     existing "loading…" status text in the row is enough. The board
     pattern is the reference if a sibling needs it later.
  3. Calls back into the UI thread via `self.call_from_thread(...)` to update
     the table rows and the detail Static.
- Refresh updates:
  - For `status == "ok"`: show `Ahead/Behind` numbers as integers; the
    Status column shows `"ok"`.
  - For unavailable states (`missing_local`, `missing_remote`, `no_remote`,
    `fetch_error`, `missing_worktree`): keep the row visible, show the
    status string in the Status column, blank ahead/behind, and surface
    `error` (if any) in the detail pane.
  - Catch exceptions around the worker body and surface them as a row-level
    error message — the TUI must not crash on transient git failures.
- Detail pane is rebuilt on row-cursor moves (`on_data_table_row_highlighted`)
  using the most recent snapshot stored on `self._last_snapshot`. Format:
  - Worktree path
  - Status (and error message, if present)
  - Ahead/behind counts
  - First N (e.g., 20) `remote_commits` as bullets
  - First N (e.g., 50) `remote_changed_paths` as bullets

### 4. Wire-in checks

- `bash -n .aitask-scripts/aitask_syncer.sh`
- `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py`
- `./ait syncer --help` should print Textual's auto-help (or a custom
  argparse `--help` if argparse is added; Textual's default suffices).
- Manual launch in tmux: `ait syncer` renders both rows and refreshes.

## Files to add or edit

- `ait` — usage, update-check skip list, dispatcher case (3 small edits).
- `.aitask-scripts/aitask_syncer.sh` — new wrapper.
- `.aitask-scripts/syncer/__init__.py` — empty package marker.
- `.aitask-scripts/syncer/syncer_app.py` — Textual app.

## Out of scope (handled by siblings)

- Sync/pull/push actions and code-agent escape hatch → **t713_3**.
- TUI registry / switcher shortcut `y` / monitor & minimonitor integration /
  `tmux.syncer.autostart` → **t713_4**.
- Helper-script whitelist touchpoints (5 layers) and config defaults →
  **t713_5**.
- User-facing website docs → **t713_6**.
- Manual verification → **t713_7**.

## Verification

- `bash -n .aitask-scripts/aitask_syncer.sh`
- `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py`
- `./ait syncer` (in tmux) renders the two-row table; numbers match `python3
  .aitask-scripts/lib/desync_state.py snapshot --fetch --json`.
- Pressing `r` triggers an immediate refresh; pressing `j` opens the TUI
  switcher; pressing `q` quits cleanly.
- Confirm unavailable-branch resilience by temporarily renaming
  `.aitask-data` (or running outside the repo) — the TUI should still
  render with a status of `missing_worktree` rather than crash.

## Final Implementation Notes

- **Actual work done:** Implemented per plan with no significant deviation. Three files created and one edited:
  - `.aitask-scripts/aitask_syncer.sh` — wrapper mirroring `aitask_codebrowser.sh`: sources `aitask_path.sh` / `python_resolve.sh` / `terminal_compat.sh`, resolves the framework Python via `require_ait_python`, asserts `textual` and `yaml`, runs `ait_warn_if_incapable_terminal`, then exec's `syncer/syncer_app.py`.
  - `.aitask-scripts/syncer/__init__.py` — empty package marker.
  - `.aitask-scripts/syncer/syncer_app.py` — `SyncerApp(TuiSwitcherMixin, App)` with a `DataTable` of two row keys (`main`, `aitask-data`) and a `VerticalScroll` detail pane. Bindings: switcher (`j` from mixin) + `r` refresh + `f` toggle fetch + `q` quit. Polling via `set_interval(self._interval, self.action_refresh)` with `_refresh_worker` running `@work(thread=True, exclusive=True)`. Detail pane caps display at 20 commits / 50 paths. Subtitle exposes `interval` and `fetch` state for visibility.
  - `ait` — three small edits: usage line for `syncer`, `syncer` added to the update-check skip list, and a dispatcher case routing to `aitask_syncer.sh`.
- **Deviations from plan:** None worth flagging. The plan's "decision: omit overlay in v1" was followed (no `LoadingOverlay`); seed row uses `"loading…"` text in the Status column instead.
- **Issues encountered:** None. Verifications all passed cleanly: `bash -n aitask_syncer.sh`, `python3 -m py_compile syncer_app.py`, `./ait syncer --help` (argparse output), and a direct `desync_state.snapshot()` import returned a live `{"refs": [...]}` payload.
- **Key decisions:** Kept the module layout single-file (`syncer_app.py`) per plan guidance; siblings can split if action handlers (t713_3) push it past comfortable size. Used `try/except` around `coordinate_to_cell_key` in `_selected_ref_name` to keep cursor-row resolution defensive — Textual's API has shifted across versions and a row-key fallback by index keeps the TUI robust.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **t713_3 (sync actions):** Action handlers should be wired onto the `BINDINGS` list in `SyncerApp` and dispatch a worker similar to `_refresh_worker`. The detail pane's `_refresh_detail` already shows `remote_commits` and `remote_changed_paths` — pull/push outcome can reuse the same Static widget for status messages, or push a transient `LoadingOverlay` for long operations. The runner extraction (t713_8) should expose a callable that takes a ref name and an action verb.
  - **t713_4 (registry/switcher/monitor):** Register `"syncer"` in `TUI_REGISTRY` (in `lib/tui_switcher.py`) so `_build_tui_list` shows it. Pick a switcher hotkey that is NOT `n` (CLAUDE.md "n is the create-task key"); current free letters in the switcher include `y`. The mixin already holds `current_tui_name = "syncer"` from `__init__`, so re-entry is wired.
  - **t713_5 (whitelist + config):** This task did NOT add the 5 helper-script whitelist touchpoints for `aitask_syncer.sh`. t713_5 must add entries to: `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`.
  - **t713_6 (docs):** The user-facing TUI list should add `syncer` only after t713_4 lands so docs match the registry.
- **Verification:** `bash -n .aitask-scripts/aitask_syncer.sh` ✅, `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py` ✅, `bash -n ait` ✅, `./ait syncer --help` renders argparse help ✅, live `desync_state.snapshot(None, False)` returns a populated `refs` list ✅. Live `ait syncer` tmux launch is a manual verification step (covered by sibling t713_7).
