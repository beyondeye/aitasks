---
Task: t622_spawn_minimonitor_in_lazygit_window.md
Base branch: main
plan_verified: []
---

## Context

When the user picks **git** from the TUI switcher (`ait board` → `j` → `g`, or selecting the "Git (lazygit)" list item), the switcher spawns a new tmux window running the configured git TUI (`lazygit` by default, per `aitasks/metadata/project_config.yaml` → `tmux.git_tui`).

Other entry points that create a new tmux window from the switcher already spawn a companion **minimonitor** pane alongside the primary command:

- `ait create` → window name `create-task` (`.aitask-scripts/lib/tui_switcher.py:417-431`)
- New explore agent → window name `agent-explore-N` (same file, `:398-415`)

The git TUI currently does not. The user wants parity: when git is launched via the switcher, a companion minimonitor should split off to the right.

### Despawn semantics — the nuance

When lazygit exits, the companion minimonitor should auto-despawn — **but only if no other primary-like pane is using the same window**. Two concrete cases:

- **User manually added a split** to the git window (shell, log tail, notes): that pane is meant to live alongside the git flow. Tearing the whole window down on lazygit exit would surprise the user.
- **User spawned a codeagent into the same window** (e.g., via `tmux split-window` of an `ait codeagent invoke …`): because the window already contains a minimonitor, `maybe_spawn_minimonitor`'s existing idempotency check (`.aitask-scripts/lib/agent_launch_utils.py:327`) skips a second spawn and the codeagent shares the existing companion. If lazygit exits first, the codeagent is still using the companion — the companion must stay.

**Cleanup rule** (applied at lazygit-exit time by a pane-scoped hook):

> List panes in the window. If any pane other than the primary (lazygit) and the companion (minimonitor) exists, the companion is still being used — kill only the primary. Otherwise, kill both the primary and the companion.

This is a conservative heuristic — we keep the companion alive when in doubt. If the user later closes the sibling pane too, they end up with a window containing only the companion, which they can close manually. The tradeoff vs. explicit reference counting: no state to maintain, no synchronization, and it works symmetrically for any "primary-like" sibling (codeagent, user shell, tail pane, etc.) without that sibling needing to know about the cleanup protocol.

### Why the helper currently rejects git

`maybe_spawn_minimonitor` (`agent_launch_utils.py:235`) rejects `"git"` for two reasons:

1. **Prefix gate** (`:289`) — `"git"` does not start with any of the default `companion_window_prefixes` (`["agent-", "create-"]`).
2. **TUI exclusion gate** (`:293`) — `"git"` is in `tui_names` (from `tui_registry.py:TUI_NAMES`), so the helper declines as it does for `board` / `monitor` / `codebrowser`.

These gates are correct for regular TUIs. `git` is a special case because it is dynamically added only when `tmux.git_tui` is configured, and lazygit benefits from a side pane.

## Approach

Three narrow changes:

1. **`maybe_spawn_minimonitor`**: (a) add a kw-only `force_companion` flag that bypasses the prefix + TUI-name gates while preserving `auto_spawn` / existing-minimonitor / pane-count gates; (b) capture and return the newly-spawned companion pane id (return type becomes `Optional[str]`).

2. **New helper `.aitask-scripts/aitask_companion_cleanup.sh`**: runs at lazygit exit via `tmux run-shell` to apply the cleanup rule above. Encapsulating the logic in a shell script (vs. inlining it in the hook) keeps the escaping sane and follows the project convention "platform-specific CLIs… encapsulate in bash scripts" (CLAUDE.md).

3. **`_switch_to`** in the switcher: when launching git, capture the primary pane id, spawn the companion (forced), and wire `remain-on-exit on` + a pane-scoped `pane-died` hook that calls the cleanup script with both pane ids.

Placing the logic inside `_switch_to` covers both entry points (`g` shortcut and list selection) because `action_shortcut_git`, `action_select_tui`, and `on_list_view_selected` all route through it.

## Changes

### 1. `.aitask-scripts/lib/agent_launch_utils.py`

Modify `maybe_spawn_minimonitor` (line 235):

- Add keyword-only parameter `force_companion: bool = False` after the existing `window_index` kw-only param.
- Wrap the prefix check (line 289) and the TUI/brainstorm exclusion check (line 293) in `if not force_companion:`.
- Leave the `auto_spawn` check (line 285), existing-minimonitor check (line 327), and pane-count check (line 330) unchanged — they must still apply.
- Change the `split-window` invocation (lines 337-341) from `subprocess.Popen` to `subprocess.run(..., capture_output=True, text=True, timeout=5)` with `-P -F "#{pane_id}"` added to the argv so the new pane's id is captured on stdout.
- Return type changes from `bool` to `Optional[str]`:
  - On successful spawn, return `result.stdout.strip()` (the companion pane_id).
  - On every early-return path (`auto_spawn` disabled, gate rejection, existing minimonitor, too many panes, tmux error), return `None`.
- Update the docstring to describe the new parameter and the new return.

Existing callers (board, codebrowser, history_screen, monitor, agentcrew_runner, and the create/explore paths in `tui_switcher.py`) never inspect the return value, so `True → str` / `False → None` is behavior-preserving.

### 2. `.aitask-scripts/aitask_companion_cleanup.sh` (NEW)

```bash
#!/usr/bin/env bash
# Pane-death cleanup for companion minimonitor panes. Called via tmux
# `pane-died` hook on a primary pane. Keeps the companion alive if any other
# sibling pane still exists in the window (e.g., a user-added shell or a
# codeagent sharing the same companion). Otherwise kills both primary and
# companion, letting tmux close the window naturally.
#
# Usage: aitask_companion_cleanup.sh <primary_pane_id> <companion_pane_id>
set -euo pipefail

primary="${1:?primary pane id required}"
companion="${2:?companion pane id required}"

# Resolve the window from the (still-dead-but-present) primary pane. If tmux
# cannot find the pane, there is nothing left to do.
window="$(tmux display-message -p -t "$primary" "#{window_id}" 2>/dev/null || true)"
if [ -z "$window" ]; then
    exit 0
fi

# Count panes in the window that are neither the primary nor the companion.
# `wc -l` padding handled with `tr -d ' '` per macOS portability notes.
others="$(tmux list-panes -t "$window" -F '#{pane_id}' 2>/dev/null \
    | grep -v -e "^${primary}$" -e "^${companion}$" \
    | wc -l | tr -d ' ')"

if [ "$others" -eq 0 ]; then
    tmux kill-pane -t "$companion" 2>/dev/null || true
fi
tmux kill-pane -t "$primary" 2>/dev/null || true
```

`chmod +x` on creation.

**Whitelisting**: this script is invoked by `tmux run-shell` from a pane hook, not by a code agent / skill. The 5-touchpoint whitelisting rule in CLAUDE.md ("Any new script… invoked by a skill must be whitelisted…") does not apply here. No entries to add to `.claude/settings.local.json`, `.gemini/policies/…`, `seed/*`, etc.

### 3. `.aitask-scripts/lib/tui_switcher.py`

Modify `_switch_to` (line 433). Running branch and non-git not-running branch stay unchanged; insert a git-specific branch:

```python
def _switch_to(self, name: str, running: bool, window_index: str | None = None) -> None:
    try:
        if running:
            target = f"{self._session}:{window_index}" if window_index else f"{self._session}:{name}"
            subprocess.Popen(
                ["tmux", "select-window", "-t", target],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif name == "git":
            self._launch_git_with_companion()
        else:
            cmd = self._get_launch_command(name)
            subprocess.Popen(
                ["tmux", "new-window", "-t", f"{self._session}:", "-n", name, cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except (FileNotFoundError, OSError):
        self.app.notify(f"Failed to switch to {name}", severity="error")
        return
    self.dismiss(name)
```

Add a new helper method on the overlay class:

```python
def _launch_git_with_companion(self) -> None:
    """Launch git TUI in a new window with a companion minimonitor. Wires a
    pane-scoped pane-died hook so that on lazygit exit, the companion is
    despawned only when no other sibling pane (user-added shell, codeagent
    sharing the companion, etc.) remains in the window."""
    cmd = self._get_launch_command("git")

    # Step 1: create the window, capture primary pane_id.
    result = subprocess.run(
        ["tmux", "new-window", "-t", f"{self._session}:", "-n", "git",
         "-P", "-F", "#{pane_id}", cmd],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        self.app.notify("Failed to launch git TUI", severity="error")
        return
    primary_pane = result.stdout.strip()

    # Step 2: spawn companion minimonitor (forced for git).
    from agent_launch_utils import maybe_spawn_minimonitor
    companion_pane = maybe_spawn_minimonitor(
        self._session, "git", force_companion=True,
    )

    # Step 3: if a companion was actually spawned, wire targeted auto-despawn.
    if companion_pane:
        # remain-on-exit keeps the dead pane around for the hook to fire.
        subprocess.Popen(
            ["tmux", "set-option", "-p", "-t", primary_pane,
             "remain-on-exit", "on"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Pane-scoped hook — disappears with the pane, no global state.
        # run-shell invokes the cleanup script with both pane ids; the script
        # decides whether to kill the companion based on sibling panes.
        script_path = str(
            Path(__file__).resolve().parent.parent / "aitask_companion_cleanup.sh"
        )
        hook_cmd = (
            f"run-shell '{script_path} {primary_pane} {companion_pane}'"
        )
        subprocess.Popen(
            ["tmux", "set-hook", "-p", "-t", primary_pane,
             "pane-died", hook_cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
```

Add `from pathlib import Path` to the imports if not already present (it is already imported at the top of the file).

`action_shortcut_git` (`:392`), `action_select_tui` (`:340`), and `on_list_view_selected` (`:352`) all funnel through `_switch_to`, so no call-site changes there.

### Edge cases (explicitly covered by the cleanup rule)

- **lazygit + companion only**: lazygit exits → cleanup sees no other panes → kills both → window closes. ✓
- **lazygit + companion + user shell**: lazygit exits → cleanup sees 1 other pane → kills only lazygit, keeps companion. Window stays open with `[companion, user shell]`. User decides when to close the rest. ✓
- **lazygit + companion + codeagent sharing companion**: lazygit exits → cleanup sees 1 other pane (codeagent) → keeps companion. Codeagent keeps using minimonitor. If the codeagent is spawned by a future flow that also wires its own cleanup hook, when the codeagent exits its hook runs the same check — by then only the companion pane remains → 0 other panes → companion is killed, window closes. ✓ (The reverse order works identically.) Today only lazygit wires this hook; extending to future codeagent flows is a natural follow-up.
- **companion not spawned (`auto_spawn: false`, pane-count overflow, tmux error)**: `companion_pane` is `None`, the hook block is skipped, the window behaves as a plain git window.
- **User manually kills lazygit pane (Ctrl-b x)**: tmux destroys the pane directly; `pane-died` fires only on command death, not on forced kill, so the hook does not run. Companion is orphaned — acceptable asymmetric trade-off matching the user's explicit intervention.
- **User manually kills the companion pane**: lazygit keeps running. Later on lazygit exit, the cleanup script's `kill-pane -t <companion>` fails silently (pane already gone); `kill-pane -t <primary>` still closes the primary. Fine.
- **Switch away and back to a running git window**: the running branch of `_switch_to` just re-selects; no re-spawn, no re-hook.

## Files to modify / add

- `.aitask-scripts/lib/agent_launch_utils.py` — `maybe_spawn_minimonitor`: add `force_companion`, capture + return pane_id.
- `.aitask-scripts/lib/tui_switcher.py` — `_switch_to`: route git through a new `_launch_git_with_companion` helper that wires the cleanup hook.
- `.aitask-scripts/aitask_companion_cleanup.sh` (NEW) — targeted cleanup invoked by the pane-died hook; `chmod +x`.

## Non-goals

- No change to `tui_registry.py` — `"git"` stays in `TUI_NAMES`.
- No change to `project_config.yaml` defaults.
- No change to `action_shortcut_create` / `action_shortcut_explore` — they still use the regular (non-forced) path and don't get auto-despawn. (If desired, the same cleanup-hook pattern can be applied there as a follow-up.)
- No whitelist changes — cleanup script is tmux-hook-invoked, not skill-invoked.
- Direct launches of `ait git` outside the switcher are untouched.
- No retroactive auto-despawn for git windows launched before this change.

## Verification

Manual (tmux/TUI interaction):

1. From `ait board`, press `j` then `g`. Expect: new `git` window; lazygit left, minimonitor right; focus on lazygit.
2. Switch away (`j` → `b`) and back (`j` → `g`). Expect: existing `git` window re-selected, no duplicates.
3. **Clean-window despawn**: quit lazygit (`q`). Expect: both lazygit and minimonitor panes vanish; window closes.
4. **User-added sibling, key scenario the user called out**: inside the git window, `Ctrl-b "` to open a shell in a new split (now `[lazygit | minimonitor | shell]`). Quit lazygit. Expect: lazygit pane is gone, minimonitor stays, user's shell stays, window stays open. Close the shell and the companion manually when done.
5. **Shared companion with codeagent (hypothetical today, testable by simulation)**: in the git window, `Ctrl-b "` + run a long-lived command (`sleep 600`). Quit lazygit. Expect: sleep pane and minimonitor both stay — companion is preserved because a sibling is alive. Kill the sleep pane: minimonitor is now alone in the window (expected; no hook on the user's manual pane to trigger full cleanup).
6. **Manual companion kill**: spawn git window (`[lazygit | minimonitor]`), kill the minimonitor pane (`Ctrl-b` arrow → `Ctrl-b x`). lazygit keeps running. Quit lazygit. Expect: window closes without errors; cleanup script's best-effort kill of the already-dead companion is silent.
7. **`auto_spawn: false`**: set `tmux.minimonitor.auto_spawn: false` in `aitasks/metadata/project_config.yaml`, restart the switcher, press `g`. Expect: lazygit-only window; quitting lazygit closes it normally (no hook wired).

## Post-implementation

Follow Step 8 (User Review) → Step 9 (Post-Implementation) of task-workflow: commit code + script + plan, then archive t622 via `./.aitask-scripts/aitask_archive.sh 622`.
