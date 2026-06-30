---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [shadow, claudeskills]
children_to_implement: [t1071_5, t1071_6, t1071_7]
created_at: 2026-06-25 00:37
updated_at: 2026-06-30 17:17
boardidx: 40
---

Add two new capabilities to the shadow-agent surface. Both originate from the
same request but are scoped differently after exploration: capability **A** is
shadow-native (a new `plan-*.md` sub-procedure); capability **B** is a *new
standalone skill* that shadow merely invokes. During planning, consider
splitting these into two children (A and B are independent).

## Background

The `aitask-shadow` skill (`.claude/skills/aitask-shadow/`) is the advisory-only
companion that watches a *followed* coding agent's tmux pane. It is static
(no `.j2`/profile machinery), `user-invocable`, and its `plan-*.md`
sub-procedures live **only in the Claude tree** (Codex/OpenCode are thin
wrappers — no cross-agent port needed). Pipeline: capture
(`aitask_shadow_capture.sh`, ~200 lines, ANSI-stripped) -> context-fetch
(`aitask_shadow_context.sh`) -> serve (Step 3 routes to inline handlers or
`plan-*.md`). Guardrail: read-only w.r.t. the *followed* pane (never sends
keystrokes); it MAY author/create tasks in its own pane. See
`aidocs/framework/shadow_agent.md` and `aidocs/framework/shadow_concern_format.md`.

## Capability A — Detect workflow/helper errors in the followed agent, mark them, offer explore-to-fix

When the followed agent is executing a skill and its captured screen shows
**tool-call errors or retries** — signs of a bug in a workflow skill definition
or a helper bash script it calls (wrong parameters, or a bug in the script
itself) — the shadow should analyze the errors, **mark** them, and **offer** to
launch `/aitask-explore` scoped to the offending skill/helper so the bug becomes
its own fix-task.

Design decisions (from exploration):
- **Detect → mark → OFFER** (user confirms before any task is created). Do NOT
  auto-launch explore. Matches the advisory ethos and
  `feedback_offer_triggered_action_immediately`.
- **No existing error/retry detection to reuse.** `monitor/prompt_patterns.py`
  only matches *awaiting-input* prompts + idle/silence; `PaneSnapshot` carries no
  error field. So this flow does its *own* text analysis of the captured screen.
  Signals to detect: `InputValidationError`, `Tool error:`, `Traceback (most
  recent call last):`, bash `error:`/stderr lines, and **repeated identical
  commands** (retry loops).
- **Reuse the existing concern block** to "mark the errors": emit the
  `===AITASK-CONCERNS===` ... `===END-CONCERNS===` format
  (`shadow_concern_format.md`, already used by `plan-challenge.md`) so the marked
  errors can be forwarded via minimonitor's concern picker.
- **Explore-to-fix is guardrail-safe**: the shadow is a full codeagent and runs
  `/aitask-explore` (or batch task creation) in *its own* pane — the advisory
  guardrail only forbids driving the *followed* pane.

Implementation outline:
1. New `.claude/skills/aitask-shadow/plan-diagnose-errors.md` sub-procedure
   (match the existing `plan-*.md` structure: header + Inputs + advisory-only
   note + methodology + concern-block output). Methodology: scan capture for the
   error/retry signals; attribute each to the likely skill/helper; emit a marked
   concern block; then offer to launch `/aitask-explore` pre-seeded with the
   buggy skill/helper paths + captured error excerpt.
2. Add a Step 3 routing entry in `SKILL.md` (e.g. "Diagnose skill/helper errors
   in the followed agent -> read and follow `plan-diagnose-errors.md`"). The
   Step 0 greeting derives from Step 3 automatically (single source of truth — do
   NOT hardcode a second copy).
3. Add a Step 1 proactive-surface trigger: when a fresh capture shows error/retry
   signals, offer this capability unprompted (suggestion-only, never auto-run).

## Capability B — `/learn`-style "learn a skill from sources" as a STANDALONE skill

Analogous to the Hermes agent `/learn` command
(https://hermes-agent.nousresearch.com/docs/user-guide/features/skills): gather
sources (local files, URLs, repo files/dirs), apply house authoring standards,
and generate a complete skill. Hermes' `/learn` is a *standards-guided prompt*
(no custom tool) that emits a `SKILL.md` to the agentskills.io spec, saved
through a write-gated tool.

Design decisions (from exploration):
- **Standalone skill, shadow invokes** (NOT a shadow sub-procedure). It needs no
  pane capture and is reusable outside shadowing. Proposed name e.g.
  `aitask-learn-skill`. The shadow gets only a thin routing entry that can launch
  it when the user asks while shadowing.
- **Reuse the fetch half**: `repo_fetch.sh` + the `aitask-reviewguide-import`
  pattern already handle GitHub/GitLab/Bitbucket + `WebFetch` fallback.
- **Output = a STATIC `.claude/skills/<name>/SKILL.md`** (minimal frontmatter:
  `name`, `description`, optionally `user-invocable`), committed to git. Default
  to static skills — a profile-aware `.j2` skill drags in goldens +
  `aitask_skill_verify.sh` complexity and should be out of scope (or an explicit
  opt-in handled by planning).
- Authoring standards to apply: `aidocs/framework/skill_authoring_conventions.md`
  (procedures in their own `.md`, no inlining; static-skill shape modeled on
  `aitask-reviewguide-import` / `aitask-shadow`).

Implementation outline:
1. New standalone skill `.claude/skills/aitask-learn-skill/SKILL.md` (static,
   user-invocable). Workflow: prompt for source(s) -> fetch via `repo_fetch.sh`
   /`WebFetch` -> analyze & extract the procedure/concepts -> ask for skill name +
   description -> generate `.claude/skills/<name>/SKILL.md` (+ optional sibling
   `.md` sub-procedures) -> stage & commit -> report the invocation path.
2. Run `./.aitask-scripts/aitask_skill_verify.sh` before committing the generated
   skill; a static skill passes trivially.
3. Add a Step 3 routing entry in `aitask-shadow/SKILL.md` that invokes
   `/aitask-learn-skill` when the user asks to learn a skill from sources while
   shadowing.
4. Per CLAUDE.md, file follow-up tasks to port the new standalone skill's stub
   surface to Codex/OpenCode (the shadow sub-procedure A is Claude-only and needs
   no port).

## Out of scope / notes
- Phase autodetection of the followed agent (deferred elsewhere) — not required;
  capability A reacts to *visible* error/retry signals only.
- Related but distinct: `t1017` (shadow steerability — over-delegation / plan
  bloat). Not folded; different problem. Capability A's "spin a concern into its
  own fix-task" is complementary and worth cross-referencing during planning.
- Cross-agent port: shadow `plan-*.md` edits (A) are Claude-only; only the new
  standalone skill (B) needs Codex/OpenCode stub follow-ups.
