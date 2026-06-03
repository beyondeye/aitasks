---
Task: t934_document_macos_awk_sed_portability_class.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Documentation follow-up to the code fixes in t931 and t932. Captures the
BSD/macOS shell portability bug-class lessons in the versioned shell docs
(`aidocs/framework/sed_macos_issues.md` and `shell_conventions.md`) so future
work catches the whole family proactively. Supersedes an ad-hoc memory note —
the guidance belongs in aidocs.

## Files Modified

### `aidocs/framework/sed_macos_issues.md`
- New sed "Incompatible Features" row for GNU-only BRE quantifiers `\?`/`\+`/`\|`,
  with a "silent footgun" callout: BSD sed treats the backslashed form as a
  literal, so the substitution no-ops and passes the raw string through with no
  error.
- "Safe Features" note clarifying that grouping `\(…\)` is portable but the
  `?`/`+`/`|` quantifiers are not — prefer `sed -E`.
- New "awk macOS Incompatibilities" section: gawk-only 3-arg
  `match(str, re, arr)` is a hard syntax error under BSD awk; also `gensub()`,
  `\<`/`\>`. Notes the 2-arg `match()` + `RSTART`/`RLENGTH` form is portable.
- New "After fixing one portability bug, sweep for the whole class" section with
  the exact grep one-liners (verified against the tree).
- "Files Fixed in t931" and "Files Fixed in t932" ledger tables, matching the
  doc's existing per-task convention.

### `aidocs/framework/shell_conventions.md`
- Bullet on silent `set -e` aborts via `"$(...)"` capture: a `warn; return 1`
  helper whose output is captured swallows the warning and propagates non-zero,
  exiting the whole script with no visible error. Fix: stderr diagnostics +
  non-fatal best-effort callers (`|| return 0` / `|| true`).
- Broadened the macOS-quirks pointer to mention the quantifiers, gawk-only awk
  features, and the sweep-the-class reflex.

## Probable User Intent

The user explicitly asked to record the portability lessons in the aidocs shell
documentation (rather than agent memory) and to wrap and push the change, so the
knowledge is versioned with the framework and discoverable by anyone editing the
scripts.

## Final Implementation Notes

- **Actual work done:** Edited the two shell docs as above; verified the
  documented grep sweeps run correctly against the current tree.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** None.
- **Key decisions:**
  - Kept guidance prose current-state (no version history), per
    `documentation_conventions.md`; the per-task "Files Fixed" ledger tables are
    the doc's deliberate, pre-existing audit-log pattern and reference the code
    tasks (t931/t932), not this documentation task.
  - Removed the earlier agent-memory note in favor of this versioned location.
