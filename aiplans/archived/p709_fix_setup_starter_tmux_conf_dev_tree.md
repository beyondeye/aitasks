---
Task: t709_fix_setup_starter_tmux_conf_dev_tree.md
Base branch: main
plan_verified: []
---

# Plan: Fix `ait setup` skipping starter tmux.conf prompt in source-tree installs (t709)

## Context

`ait setup` is supposed to offer a starter `~/.tmux.conf` (with `set -g mouse on` and other sensible defaults) to users who don't have a tmux config. The prompt comes from `setup_starter_tmux_conf()` in `.aitask-scripts/aitask_setup.sh`. In a source-tree checkout (developer running `ait setup` against their `git clone` of aitasks, or anyone running `ait setup` without going through `install.sh`), the prompt is **invisibly skipped** — no log, no warn, no prompt. The user ends up with `tmux mouse off`, which makes `ait ide` painful in Apple Terminal: clicks don't switch panes, scroll wheel doesn't work in panes, and right-click shows Terminal.app's menu instead of tmux's pane menu.

Root cause: `setup_starter_tmux_conf()` (line 2994) reads its template from `$SCRIPT_DIR/templates/tmux.conf`, but **that path is only populated by `install.sh`** (via `install_seed_tmux_conf()` at `install.sh:333`, which copies `seed/tmux.conf` into `.aitask-scripts/templates/`). In a source tree, `.aitask-scripts/templates/` does not exist, so the guard at line 2997-2999 silently returns. Meanwhile, the canonical template (`seed/tmux.conf`) **does** exist in the source tree — it's just never consulted as a fallback.

This is the same class of bug that CLAUDE.md flags under "Test the full install flow for setup helpers" (t624/t628 pattern): a setup helper that works only after `install.sh` populates a path, with no source-tree fallback.

## File to modify

- `.aitask-scripts/aitask_setup.sh` — `setup_starter_tmux_conf()` function, lines 2994-2999.

## Change

Add a fallback to `$SCRIPT_DIR/../seed/tmux.conf` when the primary `templates/` path is missing. `SCRIPT_DIR` is set at line 7 via `cd ... && pwd`, so it's an absolute path; `$SCRIPT_DIR/../seed/tmux.conf` resolves to `<repo>/seed/tmux.conf` correctly. Both install styles are then covered by exactly one path:

- **Installed tree** (`install.sh`): `seed/` is deleted at end of install, so only `.aitask-scripts/templates/tmux.conf` exists. Primary path wins.
- **Source tree** (`git clone`): `.aitask-scripts/templates/` is never created, but `seed/tmux.conf` is always present. Fallback path wins.

**Current code (`.aitask-scripts/aitask_setup.sh:2993-2999`):**
```bash
# --- Optional starter ~/.tmux.conf (opt-in, never overwrites) ---
setup_starter_tmux_conf() {
    local template="$SCRIPT_DIR/templates/tmux.conf"

    if [[ ! -f "$template" ]]; then
        return
    fi
```

**Updated code:**
```bash
# --- Optional starter ~/.tmux.conf (opt-in, never overwrites) ---
setup_starter_tmux_conf() {
    # Primary path: populated by install.sh's install_seed_tmux_conf().
    # Fallback: source-tree checkouts where seed/ is preserved.
    local template="$SCRIPT_DIR/templates/tmux.conf"
    if [[ ! -f "$template" ]]; then
        template="$SCRIPT_DIR/../seed/tmux.conf"
    fi

    if [[ ! -f "$template" ]]; then
        return
    fi
```

Rest of the function (lines 3001-3033) is unchanged.

## Verification

Per CLAUDE.md "Test the full install flow for setup helpers" — testing the helper alone is not enough; both install paths must be exercised.

1. **Source-tree case** — from this working directory (which has no `.aitask-scripts/templates/` and does have `seed/tmux.conf`), with `~/.tmux.conf` and `~/.config/tmux/tmux.conf` both absent:
   - Run `ait setup`.
   - Confirm the line `[ait] No tmux config detected at <path>.` followed by the prompt `Install aitasks-recommended starter tmux.conf? ... [y/N]` appears.
   - Answer `y` and verify the file is installed at `~/.tmux.conf` and matches `seed/tmux.conf`.
   - Cleanup: remove `~/.tmux.conf` after the test if not desired permanently.

2. **Installed-tree case** — `bash install.sh --dir /tmp/scratch709` into a fresh scratch dir, then `ait setup` inside that dir:
   - The scratch dir has `.aitask-scripts/templates/tmux.conf` (from `install_seed_tmux_conf`) but **no** `seed/` (deleted by install.sh).
   - Confirm the prompt still appears (primary path wins).
   - Confirm answering `y` installs the file (sourced from the templates path).

3. **Existing-config case** — with an existing `~/.tmux.conf` already in place:
   - Run `ait setup` and confirm the `[ait] tmux config already present at ~/.tmux.conf — leaving untouched.` line fires (no prompt).

4. **Non-TTY case** — `ait setup </dev/null`:
   - Confirm the function still returns silently without prompting (the existing `[[ ! -t 0 ]]` guard at line 3017 still handles this).

5. **Mouse-mode confirmation** (the user-visible end goal):
   - After the source-tree case (1), close the existing tmux server: `tmux kill-server`.
   - Start a new tmux session and run `tmux show-options -g | grep mouse`. Confirm output is `mouse on`.
   - Inside `ait ide`, click on a pane → focus moves; right-click on a pane border → tmux menu appears; scroll wheel inside a pane → scrolls.

## Out of scope (audit performed during exploration, not addressed here)

- `aitask_opencode_models.sh` and `aitask_add_model.sh` reference `seed/` directly but only in opt-in dev-only flows (`--sync-seed`, model registration), with explicit "seed/ not found, skipping" guards. Intentional, not bugs.
- `aitask_setup.sh:1116-1127` populates `.aitask-data/aitasks/metadata/` from `seed/` in the fresh-init branch. This is a separate code path that may degrade in installed-tree fresh-init; flag for follow-up if it ever surfaces a real failure, but out of scope for this task.

## Step 9 reference

After implementation: per the task-workflow Step 9 (Post-Implementation), the working branch is the current branch (no worktree per `fast` profile), so archival proceeds via `aitask_archive.sh 709` followed by `./ait git push`. No merge step needed.

## References

- Bug introduced: commit `38052d2a` "feature: Add opt-in starter ~/.tmux.conf to ait setup (t688_3)".
- Related guidance: CLAUDE.md → "Test the full install flow for setup helpers" (t624/t628 pattern).
- Task file: `aitasks/t709_fix_setup_starter_tmux_conf_dev_tree.md`.

## Final Implementation Notes

- **Actual work done:** Added a single fallback branch in `setup_starter_tmux_conf()` (`.aitask-scripts/aitask_setup.sh:2994`). When `$SCRIPT_DIR/templates/tmux.conf` is absent (source-tree case), the function now falls back to `$SCRIPT_DIR/../seed/tmux.conf`. Net change: 5 added lines (2 comment, 3 logic). No other files touched.
- **Deviations from plan:** None. Code matches the planned snippet exactly.
- **Issues encountered:** None.
- **Key decisions:**
  - Kept the fallback in the runtime helper rather than adding a duplicate copy step in `install.sh`. Single source of truth: `seed/tmux.conf` is the canonical template; `install.sh`'s `install_seed_tmux_conf()` copies it into `templates/` so installed users still find it via the primary path. Avoiding a duplicate `cp` to a third location keeps the picture symmetric.
  - Did not extend the audit. The two seed-reading runtime callers (`aitask_opencode_models.sh`, `aitask_add_model.sh`) are intentional dev-only flows with explicit "seed/ not found, skipping" guards. The data-branch metadata-population path at `aitask_setup.sh:1116-1127` may be a separate concern but it's a different code path with different semantics; folding it in would muddy this fix.
- **Build verification:** `shellcheck .aitask-scripts/aitask_setup.sh` reports only pre-existing infos (SC1091 in lib include, SC2015 on three pre-existing `&&...||` chains). No new warnings introduced.
- **End-to-end verification:** Ran `ait setup` in this source tree (which has no `.aitask-scripts/templates/`). With `~/.tmux.conf` and `~/.config/tmux/tmux.conf` both absent, the prompt now appears: `[ait] No tmux config detected at /Users/daelyasy/.tmux.conf.\n  Install aitasks-recommended starter tmux.conf? Enables: mouse on, ... [y/N]`. Before the fix this prompt was silently skipped.
- **Installed-tree case:** Not exercised live (requires a fresh `bash install.sh --dir /tmp/scratch709` in a clean environment). Verified by inspection: `install.sh:333 install_seed_tmux_conf()` copies `seed/tmux.conf` into `.aitask-scripts/templates/`, and `seed/` is deleted at end of install. With templates path present, the new code's first `[[ -f "$template" ]]` succeeds and the fallback branch is never taken — behavior preserved.
- **Notes for future readers:** This is the canonical pattern for any future "runtime helper that reads from a path populated by install.sh" — primary path first, source-tree fallback to `seed/` second. Worth applying preemptively to any new `install_seed_*` companion that adds a runtime-read path.
