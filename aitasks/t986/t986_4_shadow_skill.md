---
priority: medium
effort: medium
depends: [t986_3]
issue_type: feature
status: Implementing
labels: [claudeskills, claudecode, task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 16:03
updated_at: 2026-06-14 19:08
---

## Context

Child of t986 (shadow agent). This is the brain: a **non-user-invocable** skill
that drives the shadow agent. It is fed the shadowed agent's captured terminal
output and serves the user's free-form request in **one unified flow** — the
same flow covers explaining, helping answer an AskUserQuestion, or critically
interrogating a plan, depending on what the user asks. **No mode selector.**

**True deps:** t986_2 (phase-autodetection), t986_3 (context-fetch). Consumes
both. Advisory-only: the shadow never injects answers/keystrokes into the source
agent.

## Key Files to Modify / Create

- **Create** `.claude/skills/shadow/SKILL.md` with frontmatter
  `user-invocable: false` (plain `.md`, no stub/`.j2` pair — like
  `task-workflow`, `related-task-discovery`, `satisfaction-feedback`).
- Optionally split sub-procedures into sibling `.md` files under
  `.claude/skills/shadow/` (e.g. `phase-context.md`) referenced by name, only if
  SKILL.md grows large.

## Reference Files for Patterns

- `aidocs/framework/skill_authoring_conventions.md` and
  `aidocs/framework/stub-skill-pattern.md` — non-invocable skill conventions.
- Existing non-invocable skills: `.claude/skills/task-workflow/SKILL.md`
  (`user-invocable: false`), `.claude/skills/task-workflow/related-task-discovery.md`.
- Phase detection: `monitor/phase_detect.py` (t986_2).
- Context fetch: `aitask_shadow_context.sh` (t986_3).

## Implementation Plan

1. Author `SKILL.md` describing the single instruction-driven flow:
   a. Receive: the captured terminal output + the user's free-form request
      (+ resolved source task id when available, from the launcher in t986_5).
   b. Autodetect phase via `phase_detect.py` (t986_2).
   c. When the request needs source context (esp. an AskUserQuestion shown
      without its task/plan), fetch it via `aitask_shadow_context.sh` (t986_3);
      pull deeper history via `aitask_explain_context.sh` only on demand.
   d. Serve the request: explain in plain terms, OR help reason about the
      AskUserQuestion and suggest an answer, OR pose probing/adversarial/Socratic
      questions about the plan — all in the same flow, selected by the user's ask.
   e. **Advisory-only guardrail:** never send keystrokes/answers to the source
      pane; present everything to the user.
2. Keep the skill agent-agnostic where possible; gate any agent-specific runtime
   behavior behind the framework's `{% if agent %}`-style guards if needed.
3. Do NOT wire a launch-time mode enum; behavior is driven by the user's prompt.

## Verification Steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes (closure + stub-surface
  checks; a non-invocable plain-`.md` skill has no `.j2` to render).
- Dry-run the flow narrative against a captured transcript fixture (planning
  phase, AskUserQuestion-without-context, and a plan-to-challenge) to confirm the
  single flow handles all three by instruction.
- Cross-agent note: if SKILL.md ends up agent-agnostic, the Codex/OpenCode
  variants render from the Claude source automatically; only create port
  follow-ups if agent-specific surfaces are touched.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-14T19:43:57Z status=pass attempt=1 type=human
