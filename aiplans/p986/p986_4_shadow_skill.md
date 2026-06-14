---
Task: t986_4_shadow_skill.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_4_shadow_skill
Branch: aitask/t986_4_shadow_skill
Base branch: main
---

# Plan: t986_4 — shadow non-invocable skill (single instruction-driven flow)

## Context

The brain of the shadow agent: a non-user-invocable skill fed the shadowed
agent's captured output. **One unified flow** serves the user's free-form request
(explain / answer an AskUserQuestion / challenge a plan) — no mode selector.
Consumes t986_2 (phase) and t986_3 (context). Advisory-only.

## Implementation steps

1. **Create** `.claude/skills/shadow/SKILL.md`, frontmatter `user-invocable: false`,
   plain `.md` (no stub/`.j2`) — pattern: `task-workflow`, `related-task-discovery`.
2. Document the single flow:
   - Inputs: captured terminal output + user's free-form request (+ resolved
     source task id from the t986_5 launcher when available).
   - Autodetect phase via `monitor/phase_detect.py` (t986_2).
   - Fetch source context when needed via `aitask_shadow_context.sh` (t986_3);
     deeper history via `aitask_explain_context.sh` only on demand.
   - Serve the request in one flow: explain plainly, OR reason about the
     AskUserQuestion and suggest an answer, OR pose probing/adversarial/Socratic
     questions about the plan — chosen by the user's ask.
   - Advisory-only guardrail: never send keystrokes/answers to the source pane.
3. No launch-time mode enum; behavior is instruction-driven.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (closure + stub-surface checks).
- Dry-run the flow against transcript fixtures (planning, AskUserQuestion-without-context, plan-to-challenge): the single flow handles all three by instruction.
- Advisory-only: no path sends input to the source agent pane.
- Cross-agent: if SKILL.md is agent-agnostic, Codex/OpenCode render from source automatically; create port follow-ups only if agent-specific surfaces are touched.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
