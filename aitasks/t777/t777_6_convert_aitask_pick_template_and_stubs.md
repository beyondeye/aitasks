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

**Per-agent stub surfaces (per `stub-skill-pattern.md` §3g table from t777_3):**

- `.claude/skills/aitask-pick/SKILL.md.j2` (new) — the template (authoring source of truth)
- `.claude/skills/aitask-pick/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-pick/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-pick.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-pick.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: Gemini and OpenCode do NOT get a stub at `.gemini/skills/aitask-pick/SKILL.md` or `.opencode/skills/aitask-pick/SKILL.md` — those agents do not auto-discover skills as slash commands. Their stub lives in the command-wrapper file, replacing the current static `@`-include to the Claude SKILL.md. Rendered variants land at `.gemini/skills/aitask-pick-<profile>-/SKILL.md` and `.opencode/skills/aitask-pick-<profile>-/SKILL.md` and are reached via the stub's Read-and-follow instruction (not as slash commands).

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

### 3. Replace each stub surface (4 stubs per skill, per `stub-skill-pattern.md` §3b–§3d)
- **Claude stub** at `.claude/skills/aitask-pick/SKILL.md` — copy the canonical body from `stub-skill-pattern.md` §3b, substitute `<skill_short_name>=aitask-pick`, `<agent_literal>=claude`, `<agent_root>=.claude/skills`.
- **Codex stub** at `.agents/skills/aitask-pick/SKILL.md` — copy §3b with `<agent_literal>=codex`, `<agent_root>=.agents/skills`.
- **Gemini stub** at `.gemini/commands/aitask-pick.toml` `prompt` field — copy §3c, substitute `<skill_short_name>=aitask-pick`.
- **OpenCode stub** at `.opencode/commands/aitask-pick.md` body — copy §3d, substitute `<skill_short_name>=aitask-pick`.

Each stub uses Read-and-follow (per §3e) — NO slash-dispatch, NO per-agent fallback. The stubs are profile-agnostic dispatchers; the `--profile <name>` argument-override convention is handled inside the stub per §3h.

### 4. Render-and-test (paths reflect t777_3 trailing-hyphen convention)
- `./ait skill render pick --profile default --agent claude` produces `.claude/skills/aitask-pick-default-/SKILL.md` (default profile gets the `-default-` suffix per t777_3 D2; the no-suffix path is reserved for the stub).
- `./ait skill render pick --profile fast --agent claude` produces `.claude/skills/aitask-pick-fast-/SKILL.md` with the auto-confirm branch inline.
- Repeat for codex/gemini/opencode — rendered paths land at `.agents/skills/aitask-pick-fast-/`, `.gemini/skills/aitask-pick-fast-/`, `.opencode/skills/aitask-pick-fast-/`.

## Verification Steps

1. `ait skill verify` passes (validates the stub surfaces per t777_4's updated scanner).
2. `ait skillrun pick --profile fast --dry-run 777` shows the user-facing launch command `claude '/aitask-pick --profile fast 777'`.
3. Manual: render `aitask-pick-fast-` for claude, inspect the rendered file, confirm:
   - No "Profile check:" wording
   - Auto-confirm text present
   - frontmatter `name: aitask-pick-fast-` (matches the rendered dir name)
4. Manual: render same for codex, confirm `request_user_input` wording appears where AskUserQuestion would in the claude render.
5. Stub-dispatch test (Claude / Codex): type `/aitask-pick 777` (or instruction-trigger for Codex) inside a live session. Stub resolves profile, runs render, Reads `<agent_root>/aitask-pick-<active>-/SKILL.md`, follows it. Skill executes normally.
6. Stub-dispatch test (Gemini / OpenCode): type `/aitask-pick 777`. The command wrapper (`.gemini/commands/aitask-pick.toml` `prompt` field / `.opencode/commands/aitask-pick.md` body) IS the stub — it runs the resolver, renders, Reads-and-follows the rendered variant.
7. `--profile <name>` override test: type `/aitask-pick --profile fast 777`. Stub captures `fast`, strips the `--profile fast` from ARGUMENTS, dispatches to the fast variant with `777` as the forwarded ARGUMENTS.

## Notes

- This child is the pilot for the per-skill conversions (t777_8..15). Document any patterns/gotchas in `task-workflow/stub-skill-pattern.md` for siblings to leverage.
- Per CLAUDE.md "Claude-first" rule: the `.j2` template lives ONLY in `.claude/skills/aitask-pick/`. Other agents only get stubs.
