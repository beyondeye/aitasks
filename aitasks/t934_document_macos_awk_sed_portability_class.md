---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [macos, bash_scripts]
implemented_with: claudecode/opus4_8_1m
created_at: 2026-06-03 17:31
updated_at: 2026-06-03 17:31
---

Document the BSD/macOS shell portability bug-class lessons from t931 and t932 in
the framework shell docs, so future work catches the whole family proactively
instead of one instance at a time. (Replaces an ad-hoc memory note — the
guidance belongs in versioned aidocs.)

## Changes

### aidocs/framework/sed_macos_issues.md
- Added a row to the sed "Incompatible Features" table for GNU-only BRE
  quantifiers `\?` / `\+` / `\|`, plus a "silent footgun" callout explaining
  that BSD sed treats the backslashed form as a literal, so the substitution
  silently no-ops and passes the raw string through (no error).
- Added a clarifying note to "Safe Features" that grouping `\(…\)` is portable
  but the `?`/`+`/`|` quantifiers are not — prefer `sed -E`.
- New "awk macOS Incompatibilities" section: the gawk-only 3-arg
  `match(str, re, arr)` capture form is a hard syntax error under BSD awk
  (the doc recommends awk as the portable sed alternative, so this gap
  mattered); also `gensub()`, `\<`/`\>`. Notes the 2-arg `match()` +
  `RSTART`/`RLENGTH` form is portable.
- New "After fixing one portability bug, sweep for the whole class" section
  with the exact grep one-liners for the sed-quantifier and 3-arg-match
  classes.
- Added "Files Fixed in t931" and "Files Fixed in t932" ledger tables matching
  the doc's existing per-task convention.

### aidocs/framework/shell_conventions.md
- Added a bullet on silent `set -e` aborts: a `warn; return 1` helper whose
  output is captured by a caller's `"$(...)"` swallows the warning and
  propagates the non-zero status, exiting the whole script with no visible
  error. Fix: emit diagnostics to stderr and make best-effort callers
  non-fatal (`|| return 0` / `|| true`). This was the t931 silent-setup-crash
  root cause.
- Broadened the macOS-quirks pointer to mention the `\?`/`\+`/`\|` quantifiers,
  gawk-only awk features, and the sweep-the-class reflex.

## Context
Documentation follow-up to the code fixes in t931 and t932.
