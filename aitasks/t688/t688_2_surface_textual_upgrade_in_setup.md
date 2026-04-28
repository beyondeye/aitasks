---
priority: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [macos]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 10:00
updated_at: 2026-04-28 15:40
---

## Context

`ait setup` already pins `textual>=8.1.1,<9` in the venv install line (`.aitask-scripts/aitask_setup.sh:502`), but the install runs with `--quiet`. As a result, when an existing venv holds a stale Textual 8.0.0 wheel (which crashes `ait board` pick — see sibling t688_1), pip *does* upgrade it (the `>=8.1.1` constraint forces an upgrade) but the user never sees the upgrade happen. The recovery story for the bug is "re-run `ait setup`" — but without visible feedback users don't know the recovery worked.

This task makes the upgrade visible without dropping `--quiet`.

## Why split here

Pure UX touch in `aitask_setup.sh`, orthogonal to the bug fix in t688_1 and the starter tmux.conf in t688_3. Single-file change, can ship in any order relative to the other children.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — inside `setup_python_venv()`, around the existing `pip install ... 'textual>=8.1.1,<9' ...` block (lines 500–510 currently).

## Reference Files for Patterns

- `.aitask-scripts/aitask_setup.sh` — existing helpers `info`, `success`, `warn`, `die` for output; `$VENV_DIR` already in scope inside `setup_python_venv()`.
- `pip show <pkg>` standard output format: a `Version: <ver>` line is emitted on the first match; `awk '/^Version:/ {print $2}'` extracts it.

## Implementation Plan

Inside `setup_python_venv()`, surround the textual install line with before/after version capture:

```bash
# Capture installed textual version (if any) before the install line
local textual_before=""
textual_before=$("$VENV_DIR/bin/pip" show textual 2>/dev/null \
    | awk '/^Version:/ {print $2}')

"$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'

# Surface upgrade if the version changed
local textual_after=""
textual_after=$("$VENV_DIR/bin/pip" show textual 2>/dev/null \
    | awk '/^Version:/ {print $2}')
if [[ -n "$textual_before" && -n "$textual_after" && "$textual_before" != "$textual_after" ]]; then
    info "Upgraded textual: $textual_before → $textual_after"
fi
```

Notes:
- Do NOT drop `--quiet` from the pip install line.
- The `before`/`after` checks are independent: if pip wasn't installed yet (first-run), `textual_before` is empty and we silently skip the upgrade message — that's correct because there's nothing to "upgrade", just a fresh install.
- Idempotent: on a venv already at 8.1.x re-running `ait setup` does NOT print the line.

## Verification Steps

1. **Stale venv path:** In a scratch project with the existing venv, force-downgrade textual:
   ```bash
   ~/.aitask/venv/bin/pip install --quiet 'textual==8.0.0'
   ```
   Then run `./ait setup`. Expected: an `Upgraded textual: 8.0.0 → 8.1.x` line appears in the venv-step output.

2. **Already-current path (idempotency):** Run `./ait setup` a second time without changing anything. Expected: NO `Upgraded textual:` line appears (versions match).

3. **Fresh-install path:** With a brand-new venv (no textual installed before the line runs), `textual_before` is empty so the upgrade message is suppressed — the standard "Python venv ready at $VENV_DIR" success line is the only output.

4. **`--quiet` preserved:** Confirm pip's install output stays suppressed (no `Successfully installed textual-...` lines flooding the terminal).

## Acceptance Criteria

- On a stale venv where textual was <8.1.1 prior to setup, `ait setup` prints a single human-readable `Upgraded textual: <before> → <after>` line.
- On an already-up-to-date venv, the line is silent (no spurious noise).
- The `--quiet` flag on the pip install line is unchanged.
- Recovery flow is documented in this child's plan Final Implementation Notes for changelog/release-note pickup.

## Notes for sibling tasks

- The bug fix in t688_1 is what users actually need; this task just makes the recovery story (re-run `ait setup`) observably effective.
- For t688_3 (`setup_starter_tmux_conf`), this child establishes no shared infrastructure — completely independent.
