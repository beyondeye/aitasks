---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [claudeskills, whitelists]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-15 17:59
updated_at: 2026-06-15 18:21
---

## Problem

`aitask_risk_mitigation_landed.sh` is shipped as a whitelisted helper to
downstream projects via the `seed/` templates, but this repo's **own** live
Claude settings never received the entry. As a result a Claude session in the
aitasks framework repo gets a permission prompt for the script, while seeded
consumer repos do not — a dogfooding drift.

## Findings (from /aitask-explore)

The script is allowlisted in:
- `seed/claude_settings.local.json:84` — `Bash(./.aitask-scripts/aitask_risk_mitigation_landed.sh:*)`
- `seed/opencode_config.seed.json:73` — `"...risk_mitigation_landed.sh *": "allow"`
- `.codex/rules/default.rules:49` (this repo, live) — `prefix_rule(... decision = "allow" ...)`

But it is **missing** from this repo's live `.claude/settings.local.json`.

Cross-repo comparison (linked projects):

| Repo | Live Claude | Live Codex | Live OpenCode |
|------|:--:|:--:|:--:|
| aitasks (this repo) | MISSING | present (:49) | n/a (only seed/) |
| aitasks_mobile | present (:94) | present (:61) | present (opencode.json) |
| aitasks_go | present (:79) | present (:45) | present (opencode.json) |

Only the framework repo's own live Claude settings lacks the entry it ships to others.

## Fix

Add the missing line to this repo's `.claude/settings.local.json` permission
allowlist, matching `seed/claude_settings.local.json`:

```
"Bash(./.aitask-scripts/aitask_risk_mitigation_landed.sh:*)",
```

## Acceptance criteria

- This repo's live `.claude/settings.local.json` contains the
  `aitask_risk_mitigation_landed.sh` Bash allowlist entry.
- A Claude session in this repo no longer prompts for permission when
  task-workflow `planning.md` invokes the script.

## Related (separate, do NOT fold)

- t454 (refactor_bash_call_that_require_permission) — broad investigation of
  skill bash calls that *cannot* be whitelisted. This task is the narrow,
  already-whitelistable drift fix; distinct scope.
- While fixing, optionally spot-check whether other `seed/`-whitelisted helpers
  are likewise missing from this repo's live `.claude/settings.local.json`.
