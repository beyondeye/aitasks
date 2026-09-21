---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [frozen, install, setup]
created_at: 2026-09-21 22:42
updated_at: 2026-09-21 22:42
---

## Problem

`ait upgrade` (→ `install.sh --force`) stages the Claude Code SessionStart hook seed (`aitasks/metadata/claude_settings.hooks.json`) but never merges it into `.claude/settings.json`. That merge happens only in `ait setup` (`aitask_setup.sh::setup_claude_hooks`). A project that was set up before the hook shipped and has only been upgraded since has no hook. Every agent in it is invisible to the session store until it is frozen, and it then freezes into an unrestorable record.

Observed: `thinking_app` at v0.35.1 has no `.claude/settings.json` at all. All 4 of its frozen agents can neither be restored nor re-picked.

## Wanted

Make a missing hook visible and easy to fix, without silently installing executable hooks (the consent prompt is deliberate):

- After `ait upgrade`, if the hook seed exists but `.claude/settings.json` lacks the aitasks SessionStart entry, print a specific hint: "run `ait setup` to install the session hook (needed to restore frozen agents)". Verb per CLAUDE.md: repair/populate → `ait setup`.
- Consider the same check in `ait ide` startup and/or when freezing (the freeze confirmation could note "this agent can only be viewed, not restored").
- Consider a cheap `ait setup --hooks-only` style path so users don't have to re-run the whole setup.
