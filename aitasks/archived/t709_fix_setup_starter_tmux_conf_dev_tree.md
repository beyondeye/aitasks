---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_setup]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 22:45
updated_at: 2026-04-28 23:31
completed_at: 2026-04-28 23:31
---

## Symptom

`ait setup` does not display the "Install aitasks-recommended starter tmux.conf?" prompt when run from a source-tree checkout (i.e., a developer's `git clone` of the aitasks repo, or anyone running `ait setup` without going through `install.sh` first). Result: `tmux` stays at default `mouse off`, and `ait ide` is hard to use in Apple Terminal — left-click does not switch panes, scroll wheel does not work in panes, and right-click shows Terminal.app's context menu instead of tmux's pane menu.

## Root cause

`setup_starter_tmux_conf()` in `.aitask-scripts/aitask_setup.sh:2994` reads its template from:

```bash
local template="$SCRIPT_DIR/templates/tmux.conf"
```

That path (`.aitask-scripts/templates/tmux.conf`) is **only created by `install.sh`** — specifically by `install_seed_tmux_conf()` at `install.sh:333`, which copies `seed/tmux.conf` into `.aitask-scripts/templates/` during install. In a source-tree checkout, `.aitask-scripts/templates/` does not exist, so the guard at line 2997-2999 (`[[ ! -f "$template" ]] && return`) hits and the function silently returns. The user sees no prompt and no log line — the step is invisible.

The matching seed file (`seed/tmux.conf`) does exist in the source tree, and is the canonical template (introduced by commit `38052d2a` / t688_3).

## Fix

In `setup_starter_tmux_conf()`, fall back to `$SCRIPT_DIR/../seed/tmux.conf` when the templates path is missing. Both install styles are then covered by exactly one path:

- **Installed tree** (`install.sh`): `seed/` is deleted at the end of install, so only `.aitask-scripts/templates/tmux.conf` exists. Primary path wins.
- **Source tree** (developer / `git clone`): `.aitask-scripts/templates/` is never created, but `seed/tmux.conf` is always present. Fallback path wins.

Suggested code shape:

```bash
local template="$SCRIPT_DIR/templates/tmux.conf"
if [[ ! -f "$template" ]]; then
    template="$SCRIPT_DIR/../seed/tmux.conf"
fi
if [[ ! -f "$template" ]]; then
    return
fi
```

## Test plan (full install flow, per CLAUDE.md "Test the full install flow for setup helpers")

1. **Source-tree case** — from a fresh `git clone` of aitasks (or this working directory with no `.aitask-scripts/templates/` present), with no `~/.tmux.conf` or `~/.config/tmux/tmux.conf`:
   - Run `ait setup`.
   - Confirm the "Install aitasks-recommended starter tmux.conf? ..." prompt appears.
   - Answer `y` and verify the file lands at `~/.tmux.conf` (or `~/.config/tmux/tmux.conf`).
2. **Installed-tree case** — `bash install.sh --dir /tmp/scratchXY` into a fresh scratch dir, then `ait setup` inside that dir:
   - Confirm the prompt still appears (the templates path takes precedence).
3. **Existing-config case** — with an existing `~/.tmux.conf` already in place:
   - Run `ait setup` and confirm the "leaving untouched" `info` line still fires (no prompt).
4. **Non-TTY case** — pipe input to `ait setup` (`</dev/null`) and confirm the function still returns silently without prompting (existing `[[ ! -t 0 ]]` guard at line 3017).

## Audit note

Audit performed during exploration found no other instances of this class-A pattern (runtime scripts reading paths that only `install.sh` populates). The `seed/`-reading runtime references in `aitask_opencode_models.sh` and `aitask_add_model.sh` are intentional dev-only model-registration tools with explicit "seed/ not found, skipping" guards and are out of scope. The data-branch metadata-population path at `aitask_setup.sh:1116-1127` (which reads `seed/` to seed `.aitask-data/aitasks/metadata/`) is a separate, possibly degraded code path in installed-tree fresh-init and is out of scope for this task — flag for follow-up if it ever surfaces a real failure.

## References

- Bug introduced: commit `38052d2a` "feature: Add opt-in starter ~/.tmux.conf to ait setup (t688_3)"
- Related guidance: `CLAUDE.md` → "Test the full install flow for setup helpers"
