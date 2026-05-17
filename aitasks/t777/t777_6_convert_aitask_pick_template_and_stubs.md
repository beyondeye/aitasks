---
priority: high
effort: high
depends: [t777_5]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 11:59
updated_at: 2026-05-17 11:59
---

## Context

Depends on t777_1..5. The PILOT conversion. Replaces `aitask-pick`'s SKILL.md with a `.j2` template + 4 per-agent stub files. Proves the cross-agent template + stub-dispatch model end-to-end.

This is the LARGEST single-skill conversion because aitask-pick has the most profile-check blocks in the framework (Steps 0a/0b/3b/4/5/6 reference profile keys).

## Key Files to Modify

- `.claude/skills/aitask-pick/SKILL.md.j2` (new) — the template (authoring source of truth)
- `.claude/skills/aitask-pick/SKILL.md` (replace) — new stub (per the canonical pattern from t777_3)
- `.agents/skills/aitask-pick/SKILL.md` (replace) — stub for Codex
- `.gemini/skills/aitask-pick/SKILL.md` (replace) — stub for Gemini (verify path at impl time)
- `.opencode/skills/aitask-pick/SKILL.md` (replace) — stub for OpenCode

## Reference Files for Patterns

- Current `.claude/skills/aitask-pick/SKILL.md` — the content to convert
- `.claude/skills/task-workflow/stub-skill-pattern.md` (from t777_3) — canonical stub body
- `.claude/skills/task-workflow/execution-profile-selection.md` — list of all profile keys consumed during pick
- `aitasks/metadata/profiles/{default,fast,remote}.yaml` — profile key reference

## Implementation Plan

### 1. First implementation step: verify skill-loader auto-discovery
Confirm Claude / Codex / Gemini / OpenCode only auto-discover `SKILL.md` (not `*.md` or `*.j2`). If `.j2` is auto-discovered, rename to `SKILL.md.tmpl` or move the template under `.claude/skills/aitask-pick/_template/SKILL.md.j2`.

### 2. Author SKILL.md.j2 (template source)
- Copy current `.claude/skills/aitask-pick/SKILL.md` content as the base.
- Frontmatter: change `name: aitask-pick` to `name: aitask-pick-{{ profile.name }}` so the rendered file's slash command matches the per-profile directory name (e.g. `aitask-pick-fast`).
- Convert each "Profile check:" block to `{% if profile.<key> %}…{% else %}…{% endif %}`. Branches contain only straight-line text the LLM sees — no "if the active profile has X set" wording, no decisions for the LLM.
- Add `{% if agent == "..." %}` branches for tool-mapping differences (AskUserQuestion vs request_user_input for codex, etc.).
- Scan for literal `{{` and `{%` (`grep -nE '\{\{|\{%' SKILL.md`) — wrap matches in `{% raw %}…{% endraw %}`.
- Profile keys to convert (verify by grep at impl time):
  - `skip_task_confirmation` — Step 0b Format 1 (~line 44), Format 2 (~line 72)
  - `default_email` — Step 4 (resolved via task-workflow which will be templated separately in t777_7)
  - `create_worktree` — Step 5
  - `plan_preference`, `plan_preference_child` — Step 6.0 (templated in t777_7)
  - `post_plan_action`, `post_plan_action_for_child` — Step 6 Checkpoint (templated in t777_7)
  - Any others discovered by grep

### 3. Replace SKILL.md with stub (per agent × 4)
Follow `task-workflow/stub-skill-pattern.md` (from t777_3). Each stub ~15-20 lines:
```markdown
---
name: aitask-pick
description: Resolve the active profile and dispatch to the profile-specific aitask-pick variant.
---

This is a stub. Execute these steps:

1. Run `./.aitask-scripts/aitask_skill_resolve_profile.sh pick` to determine the active profile name. Capture the output as `<profile>`.

2. Run `./ait skill render pick --profile <profile> --agent claude` (replace `claude` per agent's stub) to render the profile-specific skill if needed.

3. Invoke `/aitask-pick-<profile>` with the user's original arguments. The dispatched skill executes the full workflow.

If <agent>'s slash-dispatch is unavailable: print "Profile dispatch not supported in <agent>. Run `ait skillrun pick --profile <profile>` from a shell." and abort.
```

### 4. Render-and-test
- `./ait skill render pick --profile default --agent claude` should produce `.claude/skills/aitask-pick-default/SKILL.md` (or alternatively `aitask-pick/` if you decide default has no suffix — surface in plan).
- `./ait skill render pick --profile fast --agent claude` should produce `.claude/skills/aitask-pick-fast/SKILL.md` with the auto-confirm branch inline (no "Profile check:" wording).
- Repeat for codex/gemini/opencode.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skillrun pick --profile fast --dry-run 777` shows the render call + the `/aitask-pick-fast 777` launch command.
3. Manual: render `aitask-pick-fast` for claude, inspect the rendered file, confirm:
   - No "Profile check:" wording
   - Auto-confirm text present
   - frontmatter `name: aitask-pick-fast`
4. Manual: render same for codex, confirm `request_user_input` wording appears where AskUserQuestion would in the claude render.
5. Stub-dispatch test: type `/aitask-pick 777` inside a live claude session. Stub runs, renders, dispatches to `/aitask-pick-<active>`. Skill executes normally.
6. Repeat stub-dispatch test for codex/gemini/opencode.

## Notes

- This child is the pilot for the per-skill conversions (t777_8..15). Document any patterns/gotchas in `task-workflow/stub-skill-pattern.md` for siblings to leverage.
- Per CLAUDE.md "Claude-first" rule: the `.j2` template lives ONLY in `.claude/skills/aitask-pick/`. Other agents only get stubs.
