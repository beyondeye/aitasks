---
Task: t688_2_surface_textual_upgrade_in_setup.md
Parent Task: aitasks/t688_board_pick_crash_and_starter_tmux_conf_in_setup.md
Sibling Tasks: aitasks/t688/t688_1_fix_select_set_options_crash_textual_8_0.md, aitasks/t688/t688_3_starter_tmux_conf_in_setup.md
Archived Sibling Plans: aiplans/archived/p688/p688_*_*.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan — t688_2: Surface Textual upgrade output in `ait setup`

## Context

`ait setup` already pins `textual>=8.1.1,<9` in the venv install line at `.aitask-scripts/aitask_setup.sh:502`, with `--quiet` to keep noise low on fresh installs. Pip *does* upgrade a stale 8.0 venv when re-running setup (because 8.0 doesn't satisfy `>=8.1.1`), but the user never sees the upgrade. The recovery story for the sibling bug fix t688_1 is "re-run `ait setup`" — and we want users to see proof that the upgrade happened.

This child adds visibility (a single info line) without dropping `--quiet`.

## Approach

Capture the installed textual version with `pip show textual | awk '/^Version:/ {print $2}'` immediately before and after the existing `pip install` line. If both reads succeeded and they differ, emit a single `info "Upgraded textual: <before> → <after>"`. On fresh-install paths `before` is empty so nothing is printed; on already-up-to-date paths `before == after` so nothing is printed. Idempotent and quiet by default — only speaks up when there's actually news.

## Critical Files

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` around line 500–510.

## Implementation Steps

### Step 1 — Capture before/after Textual version

Replace the existing block:

```bash
    info "Installing/upgrading Python dependencies..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'
```

with:

```bash
    info "Installing/upgrading Python dependencies..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip

    local textual_before=""
    textual_before=$("$VENV_DIR/bin/pip" show textual 2>/dev/null \
        | awk '/^Version:/ {print $2}')

    "$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'

    local textual_after=""
    textual_after=$("$VENV_DIR/bin/pip" show textual 2>/dev/null \
        | awk '/^Version:/ {print $2}')
    if [[ -n "$textual_before" && -n "$textual_after" && "$textual_before" != "$textual_after" ]]; then
        info "Upgraded textual: $textual_before → $textual_after"
    fi
```

(Keep the rest of `setup_python_venv` — the optional plotext install, the `success "Python venv ready at $VENV_DIR"` line, etc. — untouched.)

### Step 2 — No other touchpoints

- The function is private to `aitask_setup.sh` and only changes shell output; no whitelisting / 5-touchpoint changes.
- No new files or directories.

## Verification

1. **Stale venv path (the recovery flow):**

   ```bash
   ~/.aitask/venv/bin/pip install --quiet 'textual==8.0.0'
   ./ait setup
   ```

   Expected output includes a line like `Upgraded textual: 8.0.0 → 8.1.x`. The line ordering should place it between the `Installing/upgrading Python dependencies...` info line and the `Python venv ready at <VENV_DIR>` success line.

2. **Already-current path (idempotency):** Run `./ait setup` again with no version churn. Expected: NO `Upgraded textual:` line. `Python venv ready at <VENV_DIR>` is the only success indicator.

3. **Fresh-install path:** With a brand-new venv (no Textual installed before the line runs), `textual_before` is empty so the message is suppressed. The standard `Python venv ready at <VENV_DIR>` is the only output.

4. **`--quiet` preserved:** Confirm pip's verbose install output is still suppressed (no `Successfully installed textual-...` flooding the terminal). The new `info` line should be the *only* new visible signal.

## Final Implementation Notes (placeholder — to be filled in at Step 8)

- **Recovery story:** documented for changelog/release-note pickup. The line "Re-run `ait setup` to upgrade a stale Textual venv" is now self-evident from the upgrade log.

## Step 9 (Post-Implementation) reference

After Step 8 (commit code + plan separately), run:

```bash
./.aitask-scripts/aitask_archive.sh 688_2
./ait git push
```
