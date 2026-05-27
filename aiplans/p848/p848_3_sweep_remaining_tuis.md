---
Task: t848_3_sweep_remaining_tuis.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_2_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_3 — Migrate every remaining TUI to ShortcutsMixin

## Goal

Apply the pattern proven in t848_2 to every TUI under `.aitask-scripts/`
that has either hand-coded `(X)`-style labels or BINDINGS that the
editor should expose. Migrate brainstorm's `?` → `H` so the shared
shortcuts modal can claim `?`.

## Files

**New:**

- `tests/test_shortcuts_registry_coverage.sh`

**Modified:**

- `.aitask-scripts/codebrowser/codebrowser_app.py` (+ submodules with own BINDINGS)
- `.aitask-scripts/brainstorm/brainstorm_app.py` (+ `brainstorm_dag_display.py`)
- `.aitask-scripts/monitor/monitor_app.py`, `monitor_shared.py`, `monitor/minimonitor_app.py`
- `.aitask-scripts/settings/settings_app.py`
- `.aitask-scripts/stats/stats_app.py`
- `.aitask-scripts/diffviewer/diffviewer_app.py`
- `.aitask-scripts/syncer/syncer_app.py`
- `.aitask-scripts/applink/applink_app.py`
- `.aitask-scripts/agent_command_screen.py`
- `.aitask-scripts/stale_entry_modal.py`
- `.aitask-scripts/lib/tui_switcher.py`

## Step-by-step

Tackle one TUI at a time, in this order — easiest first to validate the pattern, hardest (brainstorm `?` migration) toward the end:

1. **codebrowser** — Add mixin + scope `"codebrowser"`. Migrate `Copy (R)el` / `Copy (A)bs` (lines 180-181) to `self.app.label("copy_rel", "Copy Rel")` etc. Audit sub-screens.
2. **monitor / minimonitor / monitor_shared** — Scopes `"monitor"`, `"minimonitor"`. Mixin attach. `monitor_shared.py` widgets register at construction time with the host App's scope.
3. **settings** — Scope `"settings"`. Replace the hand-composed footer string at line ~1214 with a registry-derived join: for each binding in `_TAB_SHORTCUTS`, render `f"{key}: switch tabs"`. Add missing bindings (`Binding("up","nav_up","Nav up",show=False)`) where needed.
4. **stats** — Scope `"stats"`. Replace `"Session [dim]← / → to cycle[/]"` (line ~255) similarly.
5. **diffviewer / syncer / applink** — Mixin + scope; nothing else.
6. **agent_command_screen / stale_entry_modal** — Migrate the button literals; scope = host app (board).
7. **brainstorm** — Scope `"brainstorm"`. Change `Binding("question_mark", "op_help", "Op help", key_display="?")` → `Binding("H", "op_help", "Op help")`. Update the help modal's `"[dim]Esc / ? close[/]"` to either hardcoded `"Esc / H close"` or registry-driven via `self.app.label("op_help", "close")`. Migrate any other `(X)` literals.
8. **tui_switcher** — At import time call `register_app_bindings("shared", SWITCHER_BINDINGS)` so `tui_switcher` is exposed under a synthetic `shared` scope visible from every App.
9. Add **`customizable=False`** flag support to the registry (small extension) if any binding (Esc to cancel, Ctrl+C, etc.) should not appear in the editor. Mark them at registration.

## `tests/test_shortcuts_registry_coverage.sh`

For each App listed, import the module and read `cls.BINDINGS`. Assert
every binding's `action` has been registered under the expected scope
in `keybinding_registry._DEFAULTS`. Then call `coherence_lint()` and
assert no warnings for `SHARED_ACTION_IDS` actions. (Print, don't fail,
on advisory warnings.)

## Verification

```bash
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_keybinding_registry.sh
bash tests/test_shortcut_labels.sh
# smoke launch every TUI
for tui in board monitor minimonitor codebrowser brainstorm settings stats syncer applink diffviewer; do
  echo "Launching $tui — kill after 3s"; ait $tui &
  sleep 3; kill %1 2>/dev/null
done
shellcheck tests/test_shortcuts_registry_coverage.sh
```

## Verification (for the t848_7 manual-verification sibling)

- Every TUI launches without exceptions.
- Brainstorm's `H` opens op-help; `?` does **not** open op-help.
- Settings tab-switcher footer correctly lists current tab keys.

## Step 9 — Post-implementation

Standard archival. Per-TUI sub-commits acceptable but final archival
collapses them into one merge.
