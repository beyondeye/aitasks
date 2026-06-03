---
Task: t931_fix_setup_silent_crash_and_bsd_portability.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Three macOS/BSD portability bugs in framework shell scripts, all surfaced while
running `ait setup` on macOS, were fixed:

1. `ait setup` silently aborted (under `set -euo pipefail`) right after the
   Claude permission-merge step, never printing the final "Setup complete!"
   banner — with no error output, so it looked like it might have succeeded.
2. The recommended-permissions preview printed garbled trailing `",` on every
   line (e.g. `Bash(ls:*)",`).
3. `aitask_skill_resolve_profile.sh` threw `awk: syntax error` and exited 2,
   breaking every profile-aware skill (e.g. `/aitask-wrap`) on macOS.

## Files Modified

### `.aitask-scripts/aitask_setup.sh`
- **`assemble_aitasks_instructions`**: now falls back to `seed/` for both the
  shared layer (`aitasks_agent_instructions.seed.md`) and the agent-specific
  layer (`<agent>_instructions.seed.md`) when the per-project copy under
  `aitasks/metadata/` is absent. Legacy / non-data-branch installs never copy
  those seeds into `aitasks/metadata/`, so the function used to hit its
  not-found branch.
- The "Shared instructions seed not found" `warn` is now emitted to **stderr**
  (`>&2`) so it survives callers' `"$(...)"` command substitution instead of
  being captured (and silenced) into the assembled content.
- **`update_agentsmd`** and **`update_claudemd_git_section`**: changed
  `|| return` to `|| return 0` so a future missing seed degrades to a no-op
  instead of propagating a non-zero status that `set -e` turns into a silent
  whole-script abort. This matches the codex/opencode sibling callers, which
  already used `|| true`.
- **Permission-list preview**: switched `sed 's/",\?$//'` to
  `sed -E 's/",?$//'`. BSD/macOS sed does not support the `\?` quantifier in
  BRE, so the trailing `",` was previously never stripped.

### `.aitask-scripts/aitask_skill_resolve_profile.sh`
- Rewrote the `default_profiles.<skill>` YAML value extraction to use only
  POSIX awk constructs (`~` regex test, `sub()`, `substr()`) instead of the
  GNU-awk-only 3-argument `match(str, re, arr)` capture-array form, which is a
  hard syntax error under BSD/macOS awk.

### `tests/test_agent_instructions.sh`
- Added T9b (shared seed falls back to `seed/`) and T9c (agent-specific seed
  falls back to `seed/`) as regression guards for the silent-abort fix. Full
  suite: 86/86 passing.

## Probable User Intent

The user ran `ait setup` on a macOS machine and observed it ending at the
permission-merge line, asking whether that meant success and whether there was
a final completion message. Investigation revealed the run was actually
aborting silently. The intent was to (a) make setup either complete or fail
loudly, never silently, (b) fix the cosmetic garbled permission display, and
(c) fix the related awk portability crash in the profile resolver that blocked
profile-aware skills on the same platform.

## Final Implementation Notes

- **Actual work done:** Added `seed/` fallbacks + stderr warning + non-fatal
  callers in `aitask_setup.sh`; switched the display sed to `-E`; rewrote the
  resolver awk to POSIX; added two regression tests.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** N/A (changes were already made and verified before
  wrapping).
- **Key decisions:**
  - Fixed the silent crash at its source (seed fallback) *and* added
    defense-in-depth (`|| return 0`, stderr warn) so the class of failure
    cannot recur silently.
  - Followed `aidocs/framework/sed_macos_issues.md` precedent (`sed -E`) and
    kept the resolver's parsing semantics identical while removing the gawk
    dependency.
  - This is the Claude Code source of truth; the Codex CLI (`.agents/skills/`)
    and OpenCode (`.opencode/`) trees may need the equivalent resolver
    portability fix ported as follow-up tasks.
