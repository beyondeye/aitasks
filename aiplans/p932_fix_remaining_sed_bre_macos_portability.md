---
Task: t932_fix_remaining_sed_bre_macos_portability.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Companion to t931. After fixing the permission-display `sed \?` bug in t931, a
sweep of `.aitask-scripts/*.sh` for the same GNU-only BRE quantifier surfaced 3
more instances (4 lines) that misbehave under BSD/macOS sed. All were switched
to `sed -E` with a plain `?` quantifier.

## Files Modified

### `.aitask-scripts/aitask_setup.sh` (line 1474, `check_latest_version`)
`sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/'` → `sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/'`.
On BSD sed the original substitution does not match, so `latest_version`
received the raw `  "tag_name": "v0.5.2",` line and the version comparison
produced bogus "Update available" hints.

### `.aitask-scripts/aitask_upgrade.sh` (line 56)
Same release-tag parse, same fix. On macOS it had yielded a wrong/garbage
upgrade target.

### `.aitask-scripts/aitask_update.sh` (lines 1472 and 1773)
`sed 's/^t[0-9]*_\([0-9]*_\)\?//'` → `sed -E 's/^t[0-9]*_([0-9]*_)?//'`.
This humanizes a task filename for the `ait: Update task …` commit message. On
BSD sed the optional child segment was not stripped, so `t931_5_foo_bar`
humanized to `t931 5 foo bar` instead of `foo bar`.

## Probable User Intent

While checking whether the t931 fixes needed porting to the Codex/OpenCode skill
trees, the user asked to verify the agent trees and sweep for sibling instances
of the same bug class. The trees needed nothing (they share the
`.aitask-scripts/` scripts), but the sweep found these 3 real macOS bugs, and
the user chose to fix and wrap them in the same session.

## Final Implementation Notes

- **Actual work done:** Swapped 4 sed invocations across 3 scripts from BRE with
  GNU-only `\?` to `sed -E` with `?`.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** None. Each fix was verified on the local BSD/macOS sed
  (`0.5.2` for the version parse; `foo bar` for both child and parent humanized
  names).
- **Key decisions:**
  - Confirmed via a post-fix sweep that no GNU-only `sed` BRE quantifiers (`\?`,
    `\+`, `\|`) remain in `.aitask-scripts/*.sh`.
  - Confirmed the 3-arg gawk `match()` pattern has no other real instances (the
    one in `aitask_audit_wrappers.sh` is the portable 2-arg form).
  - No per-agent porting needed: the Codex/OpenCode trees carry no shell scripts
    and invoke the shared `.aitask-scripts/` copies.
