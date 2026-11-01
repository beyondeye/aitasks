---
priority: medium
effort: medium
depends: [t2175_3]
issue_type: feature
status: Ready
labels: [sitrep]
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-11-01 17:40
---


# The sitrep skill and window (with minimonitor companion)

Child of t2175. Depends on the writer, harvest and refresh children.

## Scope
- New profile-aware skill `aitask-sitrep` (Claude Code first, per CLAUDE.md; stub + `.md.j2` pair, see `aidocs/framework/stub-skill-pattern.md` and `skill_authoring_conventions.md`; regenerate goldens; run `aitask_skill_verify.sh`). Advisory-only: never picks, pushes, edits code or sends keystrokes into other panes.
- Launches in its OWN window (not a split like the shadow) and spawns a minimonitor companion in that window; one per repo, guarded against double-spawn with a live lookup (see the shadow spawn rules in `aidocs/framework/shadow_agent.md` and `tmux_gateway.md`; all tmux through the gateways).
- On start: run refresh, read todo.md, greet with its capabilities.
- Capabilities: show Pick now / Next / Waiting; turn harvested prose into agent-derived action/watch items and write the situation text per theme; answer questions FROM THE SOURCES via the context pointers (not remembered summaries), warning when answering from a stale `checked_at`; trail status = report and offer (run `aitask-trail refresh` on user confirmation, never write the trail itself); suggestions via `aitask-backlog-roadmap`, not a reimplemented ranking; dismiss items; append every Q&A to the dated log.
- Document in `aidocs/framework/sitrep.md` and add a pointer in CLAUDE.md; user-facing docs on the website (run `check_links.py`).
- Suggest separate tasks for the codex/opencode ports.
