---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [macos, bash_scripts, ait_setup]
created_at: 2026-06-03 17:22
updated_at: 2026-06-03 17:22
---

Fix 3 remaining instances of the GNU-only `sed` BRE `\?` quantifier in framework
shell scripts. These are the same portability bug class as the permission-display
fix in t931 — BSD/macOS sed does not support `\?` in BRE, so the affected
substitutions silently fail to match on macOS. Found by sweeping for the pattern
after t931.

## Instances and macOS impact
- `aitask_setup.sh:1474` (`check_latest_version`) and `aitask_upgrade.sh:56`:
  `sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/'` parsing the GitHub release tag.
  On BSD sed the substitution does not match, so the variable receives the raw
  `  "tag_name": "v0.5.2",` line instead of `0.5.2` — producing bogus "Update
  available" hints and a wrong upgrade target on macOS.
- `aitask_update.sh:1472` and `:1773`: `sed 's/^t[0-9]*_\([0-9]*_\)\?//'` to
  humanize a task filename for the commit message. On BSD sed the optional child
  segment is not stripped, so `t931_5_foo_bar` humanizes to `t931 5 foo bar`
  instead of `foo bar`.

## Fix
Switched all four to `sed -E` with a plain `?` quantifier:
- `sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/'`
- `sed -E 's/^t[0-9]*_([0-9]*_)?//'`

Verified on BSD/macOS sed: version parse yields `0.5.2`; humanize yields
`foo bar` for both child (`t931_5_foo_bar`) and parent (`t931_foo_bar`) names.

A post-fix sweep confirms no GNU-only `sed` BRE quantifiers (`\?`, `\+`, `\|`)
remain in `.aitask-scripts/*.sh`.

## Context
Companion to t931. The Codex CLI (.agents/skills/) and OpenCode (.opencode/)
trees carry no shell scripts of their own — they invoke the shared
`.aitask-scripts/` scripts — so no per-agent porting is needed.
