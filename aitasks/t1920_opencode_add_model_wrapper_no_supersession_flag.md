---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [opencode, skills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1910
created_at: 2026-10-08 17:06
updated_at: 2026-10-08 23:46
---

## Context

t1910 added supersession recording to `/aitask-add-model` promote mode
(`.claude/skills/aitask-add-model/SKILL.md`): a new `--no-supersession` skill
flag, `--assume-registered` on the add-and-promote preview, `BLOCKED:` handling
in Step 3, an extra Step 4 option, and a new `record-supersession` subcommand of
`aitask_add_model.sh`.

The Codex and OpenCode surfaces are thin wrappers that tell the agent to read
the Claude `SKILL.md` and map tools at runtime, so they already follow the new
workflow — no workflow port is needed:

- `.agents/skills/aitask-add-model/SKILL.md` — "Read that file and follow its
  complete workflow"; `## Arguments` says "See source skill documentation".
- `.opencode/commands/aitask-add-model.md` — `@`-includes the Claude SKILL.md.
- `.opencode/skills/aitask-add-model/SKILL.md` — delegates too, **but** its
  `## Arguments` section enumerates the accepted flags, and that list is now
  stale: it omits `--no-supersession`.

## Goal

Add `--no-supersession` to the flag list in
`.opencode/skills/aitask-add-model/SKILL.md` `## Arguments` (one line; keep the
existing example). Do not copy workflow text into the wrapper — the Claude
SKILL.md stays the single source of truth.

## Verification

- `grep -n -- '--no-supersession' .opencode/skills/aitask-add-model/SKILL.md`
  finds the new entry.
- `./.aitask-scripts/aitask_audit_wrappers.sh parity` reports no new gap for
  `aitask-add-model`.
