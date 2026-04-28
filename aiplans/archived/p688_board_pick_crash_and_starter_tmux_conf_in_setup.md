---
Task: t688_board_pick_crash_and_starter_tmux_conf_in_setup.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
Strategy: split into 3 child tasks
---

# Plan — t688: split into 3 child tasks

## Context

t688 bundles three independent fixes that landed together as one task because they all surfaced from the same Mac user's first-time experience, but each can be tested, reviewed, and merged on its own. Splitting reduces review surface per child and lets us validate each fix in isolation. This plan describes the child split and what each child must contain — the implementation details have already been scoped.

## Acceptance criteria (parent-level, unchanged)

- Pressing `p` on a focused task in `ait board` on macOS opens `AgentCommandScreen` without crashing on Textual 8.0.0 AND 8.1.1.
- `ait setup` on a stale venv (Textual <8.1.1) visibly upgrades Textual to ≥8.1.1.
- Fresh-install Macs with no `~/.tmux.conf` (and no `~/.config/tmux/tmux.conf`) are offered an opt-in starter; declining or pre-existing config leaves `$HOME` untouched.
- `AgentCommandScreen` consumers in monitor and codebrowser inherit the bug fix without per-caller changes.

## Proposed child split

| ID | Subject | Why split here |
|----|---------|----------------|
| **t688_1** | Fix `AgentCommandScreen` Select crash on Textual 8.0 (defer initial-mount `set_options` via `call_after_refresh`) | Independent bug fix — single file (`.aitask-scripts/lib/agent_command_screen.py`), 2-line change. Verifiable by the headless reproducer. Highest-priority and unblocks Mac users immediately. |
| **t688_2** | Surface Textual upgrade output in `ait setup` (capture before/after version, log delta when upgraded) | Independent UX touch in `aitask_setup.sh` — orthogonal to the bug fix. Also file-isolated. Can ship without the bug fix and vice versa. |
| **t688_3** | Add opt-in starter `~/.tmux.conf` to `ait setup` (new `seed/tmux.conf`, install.sh wiring, `setup_starter_tmux_conf` helper) | Bigger surface — touches three files (`seed/tmux.conf` new, `install.sh` adds `install_seed_tmux_conf`, `aitask_setup.sh` adds `setup_starter_tmux_conf`). Needs the install-flow integration test (CLAUDE.md "Test the full install flow for setup helpers"). |

Each child gets its own plan file under `aiplans/p688/`. After this parent plan is approved I will:

1. Run the Batch Task Creation Procedure three times (one per child) with `parent=688`.
2. Revert parent t688 to `Ready`, clear `assigned_to`, release the parent lock — only the child being implemented should be `Implementing`.
3. Write `aiplans/p688/p688_1_*.md`, `p688_2_*.md`, `p688_3_*.md` with full implementation detail (per Child Task Documentation Requirements).
4. Commit child plans together: `./ait git commit -m "ait: Add t688 child implementation plans"`.
5. Skip the manual-verification-sibling offer if appropriate (live UI smoke for the bug fix is covered inside t688_1's verification — no aggregate manual-verification sibling needed; will still ask).
6. Ask the child-task checkpoint: "Start first child" vs. "Stop here".

## Per-child summaries (full plan bodies will land in `aiplans/p688/`)

### t688_1 — `agent_command_screen.py` Select crash fix

- **Issue type:** bug · **Priority:** high · **Effort:** low
- **Files:** `.aitask-scripts/lib/agent_command_screen.py` (lines 380–385)
- **Change:** Replace direct calls to `self._update_window_options(initial_session)` and `self._show_new_session_input()` inside `_populate_tmux_tab` with `self.call_after_refresh(...)` wrappers. By the next refresh tick, `Select` has mounted its internal `SelectOverlay`, so `set_options` is safe on Textual 8.0 and 8.1.x.
- **Idiom precedent:** `aitask_board.py:3497, 3534, 3541, 3561, 3956, 4391` already use `call_after_refresh` for post-mount widget mutation.
- **Audit note:** Other set_options call sites (lines 402 inside `_update_window_options`, line 422 inside `_show_new_session_input`) need no change — their later (event-driven) callers run after mount completes.
- **Verification:** Headless reproducer (per task description) under a `textual==8.0.0` scratch venv exits 0 with no `NoMatches`. Same reproducer under user's 8.1.1 venv still exits 0 (regression check). Live `ait board` press-`p` smoke test on the user's stale venv (after the t688_2 upgrade lands the venv naturally moves to 8.1.x — but the fix must work on 8.0 too, which the headless test confirms).
- **Other consumers:** Audit `aitask_board.py`, `monitor_app.py`, `history_screen.py` — all just `push_screen(AgentCommandScreen(...))`. No per-caller patches.

### t688_2 — Surface Textual upgrade in `ait setup`

- **Issue type:** chore · **Priority:** medium · **Effort:** low
- **Files:** `.aitask-scripts/aitask_setup.sh` (around line 500–510, the `setup_python_venv` Python deps install block)
- **Change:** Capture installed Textual version with `pip show textual | awk '/^Version:/ {print $2}'` before and after the install line; emit `info "Upgraded textual: $before → $after"` only when they differ. `--quiet` flag stays.
- **Verification:** In a scratch repo, force-install `textual==8.0.0` then re-run `ait setup`. Confirm the `Upgraded textual:` line appears. Re-run again — line must NOT appear (idempotent silence on already-upgraded venvs). Document `ait setup` as the recovery step in the t688_2 plan's Final Implementation Notes for changelog/release-note pickup.
- **Note:** `pip install --quiet 'textual>=8.1.1,<9'` already triggers the upgrade with current code — pip selects 8.1.1+ when 8.0 doesn't satisfy the constraint. This task only adds visibility; behavior unchanged.

### t688_3 — Starter `~/.tmux.conf` in `ait setup`

- **Issue type:** feature · **Priority:** medium · **Effort:** medium
- **Files (3):**
  - **NEW** `seed/tmux.conf` — small, well-commented starter (`mouse on`, top status bar, base-index 1, 256-color, ~30 lines).
  - `install.sh` — new `install_seed_tmux_conf()` (mirrors `install_seed_profiles` pattern) that copies `seed/tmux.conf` → `.aitask-scripts/templates/tmux.conf`. Wired into the `main()` install flow alongside the other `install_seed_*` calls, BEFORE the `rm -rf "$INSTALL_DIR/seed"` cleanup at line 1030.
  - `.aitask-scripts/aitask_setup.sh` — new `setup_starter_tmux_conf()` slotted into `main()` immediately after `setup_tmux_default_session` (current line 3040). Reads `$SCRIPT_DIR/templates/tmux.conf`. Detects existing `~/.tmux.conf` or `~/.config/tmux/tmux.conf` and skips silently. Prefers `~/.config/tmux/tmux.conf` when that dir already exists. Non-interactive runs (`! -t 0`) skip silently — never write to `$HOME` without consent.
- **CLAUDE.md compliance:**
  - **Whitelisting (5-touchpoint):** N/A — `setup_starter_tmux_conf` is a function inside the existing `aitask_setup.sh`, not a new helper script under `.aitask-scripts/`.
  - **Test full install flow:** Acceptance test MUST run `bash install.sh --dir /tmp/scratch_t688_3` first, THEN `HOME=/tmp/fakehome ./ait setup`, THEN verify `/tmp/fakehome/.tmux.conf` exists and matches the template byte-for-byte. Do NOT shortcut by hand-dropping `seed/tmux.conf` into the scratch — `install.sh` deletes `seed/` so the helper must read from the post-install location.
  - **Setup vs upgrade verb:** First-run setup, so the helper says "ait setup" in any error/recovery message — never "ait upgrade".
- **Verification (full):**
  1. Fresh install path: scratch dir, install.sh, fake `$HOME` with no tmux config → prompt shown → `y` → `~/.tmux.conf` is the byte-for-byte template.
  2. Already-configured path: pre-existing `~/.tmux.conf` (or `~/.config/tmux/tmux.conf`) → no prompt, no overwrite.
  3. Non-interactive: `< /dev/null` → silent skip, no file written.
  4. `~/.config/tmux/` exists but no config inside → write goes to `~/.config/tmux/tmux.conf`, not `~/.tmux.conf`.

## Out of scope (parent-level)

- Reworking the existing `setup_tmux_default_session` / `setup_git_tui` flows (already work).
- Forcing overwrite of an existing user `~/.tmux.conf` (always opt-in, never overwrite).
- Backporting the bug fix to older Textual versions (`<8.0`) — only 8.0+ is supported.
- Updating user-facing website docs (`website/`) — defer to a follow-up if needed; per CLAUDE.md docs-writing guidance, doc updates describe current state and can land separately.

## Step 9 (Post-Implementation) reference

Each child follows the standard archive flow: code commit + plan commit (separated), then `./.aitask-scripts/aitask_archive.sh <parent>_<child>`, then `./ait git push`. The parent t688 will auto-archive when all three children complete.
