---
priority: medium
effort: high
depends: [t848_2]
issue_type: refactor
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 17:28
updated_at: 2026-05-30 21:24
---

## Context

Third child of t848. Applies the pilot pattern proven in t848_2 to every remaining TUI: add `ShortcutsMixin`, set `_shortcuts_scope`, replace hand-coded `(X)`-style button/footer labels with `self.label(action_id, text)`, ensure every binding has a stable `action_id`. Pure repetitive migration; no design decisions.

Depends on t848_1 (registry) and t848_2 (renderer + mixin contract).

## Key Files to Modify

For each App below: add `ShortcutsMixin` to base classes, set `_shortcuts_scope`, ensure `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` is spliced into `BINDINGS`, and replace any hand-coded `(X)`-style label.

- `.aitask-scripts/codebrowser/codebrowser_app.py`:
  - Scope: `codebrowser`.
  - 18 BINDINGS (lines ~370-389) — keep current action ids.
  - `Button("Copy (R)el", ...)` and `Button("Copy (A)bs", ...)` at lines 180-181 → `Button(self.app.label("copy_rel", "Copy Rel"), ...)` etc. Add matching bindings if missing.
  - Sub-screens (`history_screen.py`, `history_detail.py`, `file_search.py`, `detail_pane.py`, `history_label_filter.py`, `code_viewer.py`): inherit App scope; only need migration if they have own BINDINGS.

- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - Scope: `brainstorm`.
  - **Move `Binding("question_mark", "op_help", "Op help", key_display="?")` (line ~2742) → `Binding("H", "op_help", "Op help")`** so the shared `?` editor (provided by `ShortcutsMixin`) takes over.
  - Update the `OperationHelpModal` instruction line that reads `"[dim]Esc / ? close[/]"` → `"[dim]Esc / H close[/]"` (or render via `self.app.label("op_help", "close")`).
  - Wizard footer `(Esc: Back)` strings: leave as-is (Esc is universal, not customizable) OR migrate to `self.app.label("escape", "Back")`. Decision: **leave** to keep diff small; Esc is special.
  - `brainstorm_dag_display.py` (line ~447): 11 BINDINGS using Unicode arrows in labels — keep labels, just register with the registry so the editor lists them.

- `.aitask-scripts/agent_command_screen.py`:
  - Buttons `Copy (P)rompt` (line ~377), `(C)opy cmd`, `(R)un in terminal` → renderer.
  - Scope inferred from the App that pushes this screen (likely `board`); register under that scope.

- `.aitask-scripts/stale_entry_modal.py`:
  - Button `(P)rune` → renderer.

- `.aitask-scripts/monitor/monitor_app.py`, `monitor_shared.py`, `monitor/minimonitor_app.py`:
  - Scopes: `monitor`, `minimonitor`. (Shared widget bindings in `monitor_shared.py` register under both via a per-instance scope passed at construction — or duplicate registration with the same action_id.)
  - No hand-coded `(X)` labels found; mixin attach only.

- `.aitask-scripts/settings/settings_app.py`:
  - Scope: `settings`.
  - Hand-composed footer at line ~1214 (`"[dim]Enter: edit | ←→: cycle | ↑↓: navigate | a/b/c/m/p/t: switch tabs[/dim]"`) → build dynamically by querying `keybinding_registry` for the action ids `edit_field`, `cycle_value`, `nav_field`, `switch_tab_*`. Where a binding doesn't exist yet (e.g. arrow navigation), add `Binding("up", "nav_up", "Nav up", show=False)` so the footer string is registry-derived.

- `.aitask-scripts/stats/stats_app.py`:
  - Scope: `stats`.
  - Hand-composed `"Session [dim]← / → to cycle[/]"` at line ~255 → registry-derived.

- `.aitask-scripts/diffviewer/diffviewer_app.py`, `syncer/syncer_app.py`, `applink/applink_app.py`:
  - Scopes: `diffviewer`, `syncer`, `applink`.
  - Mixin attach only.

- `.aitask-scripts/lib/tui_switcher.py`:
  - `TuiSwitcherMixin.SWITCHER_BINDINGS` (line ~1030) registers `j` for `tui_switcher`. Wrap registration via `register_app_bindings("shared", SWITCHER_BINDINGS)` at import time so the editor lists `tui_switcher` under a synthetic `shared` scope in every TUI.

- **NEW** `tests/test_shortcuts_registry_coverage.sh`:
  - Imports every App module, instantiates each App in `headless=True` mode (or just reads `cls.BINDINGS`), asserts every binding's `action` is registered under the expected scope via `keybinding_registry._DEFAULTS`.
  - Runs `coherence_lint()` and prints (not fails on) warnings; failures fail the test if any `SHARED_ACTION_IDS` mismatch.

## Reference Files for Patterns

- t848_2 board migration (`aitasks/archived/t848/t848_2_*.md` once archived; before that, look at `aitasks/t848/t848_2_label_renderer_and_board_pilot.md`) for the canonical change shape.
- `.aitask-scripts/lib/tui_switcher.py` — mixin attachment pattern.

## Implementation Plan

1. Tackle one TUI at a time in this order: codebrowser → monitor → minimonitor → settings → stats → brainstorm → diffviewer → syncer → applink.
2. For each: add mixin + scope, run `ait <tui>` to smoke-test, fix any regressions, commit per-TUI (optional micro-commits aid review).
3. Add `agent_command_screen.py` and `stale_entry_modal.py` last; they touch board's modal stack.
4. Write `test_shortcuts_registry_coverage.sh` and confirm it green for every scope.
5. Update `tui_switcher.py` to register `tui_switcher` action under scope `shared`.
6. Run a coherence lint pass and fix any drift introduced by typos in `action_id`s.

## Verification Steps

```bash
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_keybinding_registry.sh           # still green
bash tests/test_shortcut_labels.sh               # still green
# smoke launch every TUI
for tui in board monitor minimonitor codebrowser brainstorm settings stats syncer applink diffviewer; do
  echo "Launching $tui — close after 3 seconds to advance"; ait $tui &
  sleep 3; kill %1 2>/dev/null
done
shellcheck tests/test_shortcuts_registry_coverage.sh
```

Manual verification of `?` press in each TUI is the editor-modal job (t848_4); here only mixin attach + label render is required.

## Notes for sibling tasks

- Record the final action_id naming convention used (especially shared actions like `quit`, `refresh`) so t848_5's Settings tab table uses consistent labels.
- If any TUI's existing `tab`/`escape`/arrow bindings should NOT be user-customizable (e.g. Esc to cancel), mark them in the registry with a `customizable=False` flag and exclude from the editor's table — this is a small registry extension.
