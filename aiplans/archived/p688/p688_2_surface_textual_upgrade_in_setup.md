---
Task: t688_2_surface_textual_upgrade_in_setup.md
Parent Task: aitasks/t688_board_pick_crash_and_starter_tmux_conf_in_setup.md
Sibling Tasks: aitasks/t688/t688_1_fix_select_set_options_crash_textual_8_0.md (archived), aitasks/t688/t688_3_starter_tmux_conf_in_setup.md (archived)
Archived Sibling Plans: aiplans/archived/p688/p688_1_fix_select_set_options_crash_textual_8_0.md, aiplans/archived/p688/p688_3_starter_tmux_conf_in_setup.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 15:44
---

# Plan — t688_2: Surface Textual upgrade output in `ait setup`

## Context

`ait setup` already pins `textual>=8.1.1,<9` in the venv install line, with `--quiet` to keep noise low on fresh installs. Pip *does* upgrade a stale 8.0 venv when re-running setup (because 8.0 doesn't satisfy `>=8.1.1`), but the user never sees the upgrade. The recovery story for the sibling bug fix t688_1 is "re-run `ait setup`" — and we want users to see proof that the upgrade happened.

This child adds visibility (a single info line) without dropping `--quiet`.

## Verify-mode notes (2026-04-28)

- Existing plan reviewed: `aiplans/p688/p688_2_surface_textual_upgrade_in_setup.md`.
- Code re-checked: `.aitask-scripts/aitask_setup.sh:566` is the current location of the `textual>=8.1.1,<9 …` install line (was 502 in the original plan; lines shifted because t695_2/t695_3 inserted symlink/python-resolution logic above it). Surrounding `setup_python_venv()` body still matches plan assumptions: `info`/`success` helpers in scope, `$VENV_DIR` available, `--quiet` flag present.
- No new touchpoints introduced (still a single-file edit; helper-script whitelist checklist N/A — `setup_python_venv` is a private function inside an already-whitelisted script).
- Approach unchanged: capture pip-show version before/after the install line, emit `info "Upgraded textual: <before> → <after>"` only when both reads succeeded and they differ.

## Approach

Capture the installed textual version with `pip show textual | awk '/^Version:/ {print $2}'` immediately before and after the existing `pip install` line. If both reads succeeded and they differ, emit a single `info "Upgraded textual: <before> → <after>"`. On fresh-install paths `before` is empty so nothing is printed; on already-up-to-date paths `before == after` so nothing is printed. Idempotent and quiet by default — only speaks up when there's actually news.

## Critical Files

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` around line 564–566 (current location).

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

(Keep the rest of `setup_python_venv` — the optional plotext install, the symlink creation block, the `success "Python venv ready at $VENV_DIR"` line — untouched.)

### Step 2 — No other touchpoints

- Function is private to `aitask_setup.sh` and only changes shell output; no whitelisting / 5-touchpoint changes.
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

## Final Implementation Notes

- **Actual work done:** Added before/after `pip show textual` capture around the existing `pip install … textual>=8.1.1,<9 …` line in `setup_python_venv()` (`.aitask-scripts/aitask_setup.sh:564-580`). When both reads succeed and the versions differ, an `info "Upgraded textual: <before> → <after>"` line surfaces between `Installing/upgrading Python dependencies...` and the plotext install branch. `--quiet` is unchanged.
- **Deviations from plan:** Both version-capture assignments needed a trailing `|| true`. The script runs under `set -euo pipefail`, which propagates the pipeline's exit status to the assignment. On the fresh-install path `pip show textual` exits 1 (package not yet installed), the `awk` filter exits 0, but `pipefail` makes the overall pipeline exit 1, which then trips `set -e` on the assignment line. The plan's pseudocode would have aborted setup on fresh installs. Fix: append `|| true` to both `textual_before=…` and `textual_after=…` assignments. A two-line comment was added above the `before` block to document the rationale.
- **Issues encountered:** Caught the `set -e` / `pipefail` interaction during a standalone smoke test of the three paths (fresh / stale / idempotent) before running `./ait setup`; the bash trace showed the script exiting silently right after the `before=` assignment on the fresh-install path. Once `|| true` was added, all three paths behaved as specified.
- **Key decisions:** Stuck with `pip show textual | awk` rather than `pip list --format=json | jq …` to keep the dependency footprint identical (no jq required); awk is already used elsewhere in `setup_python_venv()`. Kept the inline comment short — only the `|| true` rationale, since the rest of the block is self-explanatory.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** Pattern for safely capturing a tool's textual output inside a `set -euo pipefail` script: `var=""; var=$(cmd 2>/dev/null | awk …) || true`. The leading empty `local var=""` is required so the variable is defined even when the `|| true` short-circuits, and the post-pipeline `|| true` is required so a failing `cmd` (exit ≠ 0) doesn't abort the script via `pipefail`. Future setup-flow helpers that need to compare a "before" snapshot against an "after" snapshot of pip-managed packages should use the same pattern.

- **Recovery story:** Documented for changelog/release-note pickup. The line "Re-run `ait setup` to upgrade a stale Textual venv" is now self-evident from the upgrade log.

## Step 9 (Post-Implementation) reference

After Step 8 (commit code + plan separately), run:

```bash
./.aitask-scripts/aitask_archive.sh 688_2
./ait git push
```
