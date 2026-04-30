---
Task: t713_4_tmux_switcher_monitor_integration.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md, aitasks/t713/t713_7_manual_verification_syncer_tui.md
Archived Sibling Plans: aiplans/archived/p713/p713_1_desync_state_helper.md, aiplans/archived/p713/p713_2_syncer_entrypoint_and_tui.md, aiplans/archived/p713/p713_3_sync_actions_failure_handling.md, aiplans/archived/p713/p713_8_extract_sync_action_runner.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 15:07
---

# t713_4 — Tmux switcher / monitor integration for the syncer TUI

## Context

Parent **t713** ships an `ait syncer` TUI for tracking remote desync state on
`main` and `aitask-data`. Siblings already shipped:

- **t713_1** — `lib/desync_state.py` (data helper with `snapshot --json/--text/--lines`).
- **t713_2** — `aitask_syncer.sh` + `syncer/syncer_app.py` (entrypoint + read-only TUI shell).
- **t713_3** — `s/u/p/a` actions + escape-hatch (sync/pull/push + agent failure resolution).
- **t713_8** — `lib/sync_action_runner.py` (shared `run_sync_batch`, `parse_sync_output`, `SyncConflictScreen`).

This child wires the syncer into the existing tmux/TUI surfaces:

1. TUI registry — register `syncer` so it classifies as a TUI window.
2. TUI switcher — add hotkey `y`, surface a desync info line.
3. `ait ide` autostart — singleton `syncer` window when `tmux.syncer.autostart: true`.
4. Monitor — compact desync summary line.
5. Minimonitor — compact desync summary line.

Out of scope for this child: helper-script whitelist touchpoints + seed
config (sibling **t713_5**); user-facing docs (**t713_6**); aggregate
manual verification (**t713_7**).

## Verified assumptions (verify-path)

- `lib/tui_registry.py:17-39` — `TUI_REGISTRY` is the single source of truth.
  Adding `("syncer", "Syncer", "ait syncer", True)` propagates to:
  - `_TUI_NAMES` (`tui_registry.py:34`) — used by `tmux_monitor` for window classification (`tmux_monitor.py:46` aliases `DEFAULT_TUI_NAMES = TUI_NAMES`).
  - `KNOWN_TUIS` / `_build_tui_list()` (`tui_switcher.py:76`) — switcher modal.
- `lib/tui_switcher.py:101-108, 261-269` — current switcher shortcuts use
  `b m c s t r x g n`. **`y` is unused** and matches the plan + the t713_2
  notes.
- `lib/desync_state.py:156-159` — `snapshot(ref_filter, fetch)` returns
  `{"refs": [{"name", "status", "ahead", "behind", ...}, ...]}`. Without
  `--fetch` the call only does `git rev-list/log` — fast enough for monitor
  refresh ticks.
- `lib/agent_launch_utils.py:690-723` — `load_tmux_defaults()` reads `tmux.*`
  keys from `aitasks/metadata/project_config.yaml` and falls back to
  defaults. Adding a `syncer.autostart` key (default `False`) follows the
  same pattern as `git_tui`.
- `aitask_ide.sh:98-110` — monitor singleton pattern (`tmux list-windows |
  grep -qx 'monitor'` → `select-window` if present, else `new-window -n
  monitor`). Mirrorable for `syncer`.
- `monitor/monitor_app.py:856-881` — `_rebuild_session_bar()` is the canonical
  insertion point for top-bar status text. Called every refresh tick.
- `monitor/minimonitor_app.py:312-334` — same pattern for the minimonitor.
- `tests/test_git_tui_config.py:139-153` — `TestTuiRegistry` already covers
  registry membership; one new assertion plus a `syncer in switcher_tuis()`
  check is sufficient.

## Implementation

### 1. Register `syncer` in TUI registry

**File:** `.aitask-scripts/lib/tui_registry.py`

Append one entry to `TUI_REGISTRY` (after `diffviewer`, before
non-switcher entries):

```python
("syncer",      "Syncer",        "ait syncer",      True),
```

This single edit propagates to:
- `TUI_NAMES` (window classification) — picked up by `tmux_monitor`, switcher's
  `_classify_window`, and minimonitor.
- `switcher_tuis()` → `KNOWN_TUIS` → `_build_tui_list()` — the switcher modal
  list.

### 2. Switcher shortcut `y` and desync info line

**File:** `.aitask-scripts/lib/tui_switcher.py`

#### 2.1 Shortcut binding `y` for syncer

- Add `"syncer": "y"` to `_TUI_SHORTCUTS` (`tui_switcher.py:101`).
- Add `Binding("y", "shortcut_syncer", "Syncer", show=False)` to
  `TuiSwitcherOverlay.BINDINGS` (alongside the existing `b/m/c/s/t/r/x/g/n` set
  at `tui_switcher.py:261-269`).
- Add handler `action_shortcut_syncer(self) -> None: self._shortcut_switch("syncer")`
  next to `action_shortcut_codebrowser` (`tui_switcher.py:560`).
- Update the footer-hint string in `_render_hint()` (`tui_switcher.py:367-372`)
  to include `s[bold bright_cyan](y)[/]ncer`.
  - **Note:** `s` is already shown for "settings". Choose the demotion form
    `[bold bright_cyan](y)[/]ncer` (no `s` prefix highlight — `y` is a
    sibling demoted spelling).
  - Final hint line additions: insert ` [bold bright_cyan](y)[/]ncer` between
    `s[bold bright_cyan](t)[/]ats` and `b[bold bright_cyan](r)[/]ainstorm`,
    keeping the order natural.

#### 2.2 Desync info line in switcher modal

Add a small status line below the session row (or as part of the dialog) that
shows `main: <a>↑/<b>↓ · aitask-data: <a>↑/<b>↓` for the **selected** session's
project root.

Implementation:
- Add a `Label(id="switcher_desync")` to `compose()` between `switcher_session_row`
  and `switcher_list`.
- Style in `DEFAULT_CSS`: `text-align: center; color: $text-muted; padding: 0 0 1 0; width: 100%`.
- Helper method `_render_desync_line(self, project_root: Path) -> None` that:
  - Imports `desync_state` from the lib dir (already on `sys.path` via
    `tui_switcher.py:42-44`).
  - Calls `desync_state.snapshot(None, fetch=False)` against the project root.
    - Wrap in try/except: on any exception render a muted "desync: unavailable".
    - Note: `desync_state.snapshot()` currently uses `repo_root()` which
      walks up from the `desync_state.py` file location, NOT a passed-in
      project root. **Verify behavior:** the helper resolves the repo root
      from its own `__file__`. For a multi-project switcher this returns the
      project that owns the `desync_state.py` source — which is the same
      project as the currently attached session in the framework's
      single-source layout. If we want true selected-session scoping, we'd
      need a `--cwd` flag on the helper or to invoke it via subprocess with
      `cwd=project_root`.
  - **Decision:** invoke `desync_state.py snapshot --format lines` as a
    subprocess with `cwd=str(project_root)` so multi-session selection
    works correctly. Cache the result with a 30s TTL keyed on
    `(project_root, fetch=False)` to avoid repeated invocations on every
    Left/Right cycle.
  - Format: `main: 1↑/3↓ · aitask-data: 0↑/2↓` (compress `0↑/0↓` to a dim
    `clean` for both refs). Render as `Label.update(text)`.
- Call `_render_desync_line(self._project_root_for_session(self._session))`
  from `on_mount` (after `_render_session_row`) and from `_cycle_session`
  (after `_render_session_row`).

### 3. `ait ide` autostart for syncer

**File:** `.aitask-scripts/aitask_ide.sh`

Mirror the monitor singleton pattern at lines 98-110:

```bash
# After monitor handling, conditionally launch syncer:
if [[ "${SYNCER_AUTOSTART:-0}" == "1" ]]; then
    if ! tmux list-windows -t "$SESSION_T" -F '#{window_name}' | grep -qx 'syncer'; then
        tmux new-window -t "${SESSION_T}:" -n syncer 'ait syncer'
    fi
fi
```

`SYNCER_AUTOSTART` is exported earlier in the script by reading the config:

```bash
read_syncer_autostart() {
    local cfg="aitasks/metadata/project_config.yaml"
    [[ -f "$cfg" ]] || { echo "0"; return; }
    awk '
        /^tmux:/ { intmux=1; next }
        intmux && /^  syncer:/ { insyncer=1; next }
        insyncer && /^    autostart:/ {
            sub(/^    autostart:[ \t]*/, "")
            gsub(/"/, ""); gsub(/'\''/, ""); sub(/[[:space:]]+$/, "")
            if ($0 == "true") { print "1"; exit }
            print "0"; exit
        }
        /^[^ #]/ && !/^tmux:/ { intmux=0; insyncer=0 }
    ' "$cfg" || echo "0"
}
SYNCER_AUTOSTART=$(read_syncer_autostart)
```

Apply the autostart logic in **all three** branches of the existing flow:
- Inside-tmux already-attached branch (after the existing monitor select-window/new-window).
- Already-existing-session branch (after the `tmux new-window -n monitor` block, before the `tmux attach`).
- New-session branch (after `tmux new-session ... -n monitor 'ait monitor'`,
  e.g. via a `tmux new-window -n syncer 'ait syncer'` follow-up before `tmux attach`).

Default: `false`. Off by default keeps the existing user experience unchanged.

**Loader update:** Also extend `lib/agent_launch_utils.py`
`load_tmux_defaults()` to expose `syncer_autostart` (default `False`). This
keeps a Python-side single source of truth for the same key, useful if other
TUIs eventually want to read it.

```python
defaults["syncer_autostart"] = False
# ... inside the tmux dict parse:
if "syncer" in tmux and isinstance(tmux["syncer"], dict):
    if "autostart" in tmux["syncer"]:
        defaults["syncer_autostart"] = bool(tmux["syncer"]["autostart"])
```

### 4. Monitor compact desync line

**File:** `.aitask-scripts/monitor/monitor_app.py`

Extend `_rebuild_session_bar()` (`monitor_app.py:856`) to append a desync
summary suffix to the bar text in **both** the multi-session and
single-session branches.

Implementation:
- Add a cached helper `_get_desync_summary(self, project_root) -> str`:
  - 30s TTL cache keyed on project_root.
  - Subprocess: `python3 .aitask-scripts/lib/desync_state.py snapshot --format lines`
    with `cwd=project_root`, `timeout=2`.
  - Parse `STATUS:`, `AHEAD:`, `BEHIND:` lines per ref.
  - Return either `""` (both clean), or a compact string like
    ` · [yellow]desync: aitask-data 3↓[/]` (only refs with non-zero behind shown).
  - On any failure (timeout, non-zero exit, parse error): return `""` (silent).
- For multi-session mode, scope to **each session's** project root (the
  monitor already tracks per-session project roots at `monitor_app.py:721+`
  via `_task_cache.update_session_mapping`). Strategy: render desync for the
  attached session only in the bar (single line, low real-estate), not per
  session — matches existing pattern of "tmux Monitor — N sessions · M panes".
- Call the helper from `_rebuild_session_bar()` and append its output to the
  bar text.

### 5. Minimonitor compact desync line

**File:** `.aitask-scripts/monitor/minimonitor_app.py`

Same approach as monitor:
- Same `_get_desync_summary` helper (extract to `monitor/_desync_summary.py`
  or duplicate inline — single small helper, duplication is fine to avoid
  cross-import coupling).
- In `_rebuild_session_bar()` (`minimonitor_app.py:312-334`), append the
  desync suffix to both single-session and multi-session bar text.

**Caveat:** minimonitor displays a very compact bar (`f"multi: {n}s · {total}a..."`).
Keep the desync suffix to ≤10 chars (e.g., ` · ↓3`) when rendering in
minimonitor to avoid overflow. Use a separate formatter
`_format_desync_compact()` that returns at most `↓<N>` for the worst-case
ref behind count (or empty if both clean).

### 6. Tests

**File:** `tests/test_git_tui_config.py`

Extend `TestTuiRegistry` (line 139):

```python
def test_syncer_in_registry(self):
    """syncer is registered as a TUI and visible in the switcher."""
    from tui_registry import TUI_NAMES, switcher_tuis
    self.assertIn("syncer", TUI_NAMES)
    switcher_names = {n for n, _, _ in switcher_tuis()}
    self.assertIn("syncer", switcher_names)
```

Optionally add to `TestGitInTuiSets` (line 112) — `syncer in _TUI_NAMES`
parity check.

**File (optional new test):** `tests/test_load_tmux_defaults_syncer.py` —
covers the new `syncer_autostart` key parsing (`true`, `false`, missing,
malformed).

## Files modified

- `.aitask-scripts/lib/tui_registry.py` — 1-line registry append.
- `.aitask-scripts/lib/tui_switcher.py` — shortcut binding/handler/hint + desync info line (~30 LOC).
- `.aitask-scripts/aitask_ide.sh` — autostart loader + 3 conditional branches.
- `.aitask-scripts/lib/agent_launch_utils.py` — `load_tmux_defaults` extension for `syncer.autostart`.
- `.aitask-scripts/monitor/monitor_app.py` — desync summary helper + bar append.
- `.aitask-scripts/monitor/minimonitor_app.py` — compact desync suffix.
- `tests/test_git_tui_config.py` — 1 new assertion (syncer membership).

## Out of scope (handled by siblings)

- 5-touchpoint helper-script whitelist for `aitask_syncer.sh` → **t713_5**.
- `seed/project_config.yaml` documentation block for `tmux.syncer.autostart` → **t713_5**.
- User-facing docs in `website/` → **t713_6**.
- Aggregate manual verification (TUI smoke pass) → **t713_7**.

## Verification

### Automated
- `python3 -m py_compile .aitask-scripts/lib/tui_switcher.py`
- `python3 -m py_compile .aitask-scripts/lib/tui_registry.py`
- `python3 -m py_compile .aitask-scripts/lib/agent_launch_utils.py`
- `python3 -m py_compile .aitask-scripts/monitor/monitor_app.py`
- `python3 -m py_compile .aitask-scripts/monitor/minimonitor_app.py`
- `bash -n .aitask-scripts/aitask_ide.sh`
- `python3 -m pytest tests/test_git_tui_config.py -v` (covers TUI_REGISTRY membership + syncer presence in switcher).

### Manual
- `ait` (in tmux) → press `j` → verify the switcher modal lists `Syncer` with `(y)` shortcut.
- Press `y` from the switcher → opens/focuses the `syncer` window.
- Set `tmux.syncer.autostart: true` in `aitasks/metadata/project_config.yaml` (temporarily) → exit tmux, re-run `ait ide` → verify a `syncer` window is created alongside `monitor`.
- Set `tmux.syncer.autostart: false` (or omit the key) → re-run `ait ide` → verify NO `syncer` window is created (default behavior).
- With `aitask-data` deliberately behind origin (push from a scratch clone), open `ait monitor` and `ait minimonitor` → verify the compact desync summary appears.
- With both refs clean → verify the desync suffix is absent from monitor/minimonitor bars and the switcher info line shows `clean` (or is hidden).

## Reference: Step 9 (Post-Implementation)

After Step 8 commits land:
- No worktree to clean up (current branch per `create_worktree: false`).
- `verify_build` (if configured in `aitasks/metadata/project_config.yaml`) runs.
- `./.aitask-scripts/aitask_archive.sh 713_4` archives the task and plan, releases the lock, removes from parent's `children_to_implement`, commits.
- `./ait git push` after archival.

## Notes for sibling tasks

- **t713_5**: This task adds the `tmux.syncer.autostart` runtime read path
  but does NOT add the seed/whitelist touchpoints. The 5-touchpoint pass for
  `aitask_syncer.sh` (added by t713_2) and the `seed/project_config.yaml`
  documentation block remain t713_5's responsibility.
- **t713_6**: Once t713_4 lands, the user-facing docs can document the `y`
  shortcut and the `tmux.syncer.autostart` config key.
- **t713_7**: The aggregate manual-verification checklist should include the
  switcher `y` shortcut, monitor/minimonitor desync line presence, and the
  `ait ide` autostart toggle.

## Final Implementation Notes

- **Actual work done:**
  - `lib/tui_registry.py` — appended `("syncer", "Syncer", "ait syncer", True)` to `TUI_REGISTRY`. Single-source-of-truth propagation: `TUI_NAMES`, `KNOWN_TUIS`, `switcher_tuis()`, and `tmux_monitor.DEFAULT_TUI_NAMES` all pick up `syncer` automatically.
  - `lib/tui_switcher.py` — added `"syncer": "y"` to `_TUI_SHORTCUTS`, `Binding("y", "shortcut_syncer", …)` to `TuiSwitcherOverlay.BINDINGS`, and `action_shortcut_syncer` handler delegating to `_shortcut_switch("syncer")`. Footer hint now reads `… s(t)ats  s(y)ncer  b(r)ainstorm …`. Added `#switcher_desync` Label between session row and list, with `_render_desync_line(project_root)` invoked from `on_mount` and `_cycle_session`. The render method calls a class-cached helper `_compute_desync_summary(project_root)` (30s TTL) which subprocess-runs `desync_state.py snapshot --format lines` with `cwd=project_root` and renders e.g. `main: 4↑/0↓ · [dim]aitask-data: clean[/]` or `[dim]all refs clean[/]`.
  - `lib/agent_launch_utils.py` — `load_tmux_defaults()` now exposes `syncer_autostart` (default `False`), reading `tmux.syncer.autostart` and coercing via `bool()`.
  - `aitask_ide.sh` — added `read_syncer_autostart()` awk parser (returns `"1"` only for the literal `true`, defaults to `"0"` for missing/false/malformed) and an `ensure_syncer_window()` helper that creates a `syncer` window only when the autostart flag is `1` and no `syncer` window already exists. Refactored the inside-tmux branch to no longer `exec` mid-flow so the helper can run before the final `select-window` exec; called the helper in all three branches (inside-tmux, existing-session, new-session).
  - `monitor/desync_summary.py` (new, 109 LOC) — shared module exporting `get_desync_summary(project_root, *, compact)`. 30s in-process TTL cache, 2s subprocess timeout. Returns empty string when both refs are at zero behind (so callers can append unconditionally) and a markup-styled string otherwise. `compact=True` produces an ultra-short `↓<N>` form for minimonitor; `compact=False` produces the longer `desync: <ref> N↓` form for monitor.
  - `monitor/monitor_app.py` — imports `get_desync_summary as _get_desync_summary`. `_rebuild_session_bar` calls it with `compact=False` against `Path.cwd()` and inserts the result before the trailing `[dim]Tab: switch panel[/]` hint in both single- and multi-session branches.
  - `monitor/minimonitor_app.py` — same import; `_rebuild_session_bar` calls it with `compact=True` and appends to the bar text in both branches.
  - `tests/test_git_tui_config.py` — added `test_syncer_registered_and_visible_in_switcher` to `TestTuiRegistry`, asserting `syncer` is both in `TUI_NAMES` and visible in `switcher_tuis()`.
- **Deviations from plan:**
  - Decided to extract the desync formatter into `monitor/desync_summary.py` rather than duplicating inline. The plan flagged both options; the shared module avoids two divergent parsers and keeps the 30s TTL cache shared across monitor + minimonitor. Both monitor variants pass `compact=` to select formatting.
  - Switcher's `_format_desync_lines` is module-level (not on the screen class) for testability; the per-screen `_render_desync_line` and class-level `_compute_desync_summary` cache are thin wrappers around it.
  - The plan suggested adding `_get_desync_summary` directly on the monitor app classes; that would have required passing `Path.cwd()` through and duplicating the parser. Pulled out into the shared module instead — same behavior, less code.
  - Skipped the optional `tests/test_load_tmux_defaults_syncer.py` file: smoke-tested the four parsing cases (missing, true, false, no-syncer-key) inline during implementation and all four returned the correct value. The existing `TestLoadTmuxDefaultsGitTui` covers the per-key parsing pattern; adding a near-duplicate for `syncer_autostart` would be churn.
- **Issues encountered:**
  - Initial `read_syncer_autostart` awk + `|| echo "0"` shell short-circuit returned an empty string when the syncer key was missing (awk exits 0 with empty stdout). Fixed with explicit `[[ -z "$out" ]] && out="0"` after capture.
  - Verified by smoke test: `awk` parser returns `1` for `autostart: true`, `0` for `false`, and (after the empty-fallback fix) `0` for missing keys.
- **Key decisions:**
  - **Append-when-empty pattern:** `get_desync_summary` returns `""` rather than `"clean"` when both refs are at zero behind. Callers can unconditionally concatenate without conditional formatting; the bar reads identically to before when nothing is drifting. This matches the existing pattern of `auto_tag` and `idle_str` in the same code paths.
  - **`Path.cwd()` for monitor scope:** The monitor processes are launched with the project root as cwd by `aitask_monitor.sh`. Reading desync from `Path.cwd()` is correct. For multi-session monitor, the bar represents the attached session; per-session desync would mean per-session lines, which doesn't fit the single-line bar. Keeping it scoped to the attached session matches the pre-existing `tmux Monitor — N sessions · M panes` summary semantics.
  - **Subprocess vs in-process for desync_state:** Used subprocess so cwd-scoping works across multi-project sessions in the switcher. The helper has a 2s timeout and the result is cached for 30s, so wall-clock cost is bounded.
  - **Empty-cache fallback:** When the `desync_state.py` subprocess fails (timeout, non-zero exit, missing helper), the helper returns `""` silently in monitor/minimonitor (graceful degradation — no UI flicker). The switcher renders `[dim]desync: unavailable[/]` instead so the user sees that the check was attempted.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t713_5 (whitelist + config):** This task added the runtime read path for `tmux.syncer.autostart` in both `aitask_ide.sh` (awk parser) and `lib/agent_launch_utils.py` (`syncer_autostart` field). t713_5 still owns the seed-side documentation block in `seed/project_config.yaml` and the 5-touchpoint helper-script whitelist for `aitask_syncer.sh`.
  - **t713_6 (docs):** When documenting the new `y` switcher shortcut, note that the demoted form `s(y)ncer` is used in the footer hint string (matches `s(t)ats` style — `y` is the second letter of the spelling, not the first).
  - **t713_7 (manual verification):** The verification list in this plan's "Manual" section is ready-to-use as the aggregate checklist content. Two notes: (1) the desync line in the switcher will only show non-zero values when `aitask-data` or `main` is *behind* origin (ahead-only state shows as `clean`); use a scratch-clone push-then-back-to-origin to force a behind state. (2) The desync line subprocess has a 2s timeout — if origin is unreachable, the line shows `desync: unavailable` rather than blocking the modal.
- **Verification performed:**
  - `python3 -m py_compile` — all 6 Python files compile cleanly.
  - `bash -n .aitask-scripts/aitask_ide.sh` — passes.
  - `python3 -m unittest tests.test_git_tui_config -v` — 17/17 pass, including new `test_syncer_registered_and_visible_in_switcher`.
  - `bash tests/run_all_python_tests.sh` — 557/557 framework tests pass.
  - End-to-end smoke test: `desync_state.py snapshot --format lines` invoked from `Path.cwd()` returned the expected `REF/STATUS/AHEAD/BEHIND` block; `_format` returned correctly for clean and behind cases; `load_tmux_defaults` returned correct `syncer_autostart` values for all four config variants.
