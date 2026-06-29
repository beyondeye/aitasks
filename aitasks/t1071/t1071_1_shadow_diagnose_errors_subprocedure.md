---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [shadow, claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-29 12:05
updated_at: 2026-06-29 15:35
---

Capability A of t1071: give the shadow agent a sub-procedure that detects
workflow/helper **errors** in the followed agent's captured screen, **marks**
them as a forwardable concern block, and **offers** to launch `/aitask-explore`
scoped to the offending skill/helper so the bug becomes its own fix-task.
Detect -> mark -> OFFER (user confirms; never auto-launch). Claude-only — no
cross-agent port (shadow `plan-*.md` sub-procedures live only in the Claude tree;
Codex/OpenCode shadow are thin wrappers redirecting there).

## AC revision (after plan review 2026-06-29)

These supersede the original outline below where they conflict:
- **On-request only — NOT proactive.** Reached only when the user asks the shadow
  to diagnose what is going wrong (Step 3 routing). Do **not** add a Step 1
  proactive-surface trigger; the shadow never emits unsolicited error concerns.
- **User picks which concerns to act on.** When triggered, present the candidate
  concerns (concern-block format, like plan review) and let the user choose which —
  if any — warrant a fix-task.
- **One offer behavior (v1):** `/aitask-explore` with a seed prompt only. Drop the
  "or batch task creation" branch (possible later enhancement).
- **Negative-control fixture required** in verification (benign error-shaped text
  must NOT emit a concern block).
- **Docs stay capability-level:** `shadow_agent.md` gets one bullet, no signal-list
  duplication.

## Context

The `aitask-shadow` skill (`.claude/skills/aitask-shadow/`) is the advisory-only
companion watching a *followed* coding agent's tmux pane. It is static (no
`.j2`/profile machinery), `user-invocable`. Pipeline: capture
(`aitask_shadow_capture.sh`) -> context-fetch (`aitask_shadow_context.sh`) ->
serve (`SKILL.md` Step 3 routes to inline handlers or `plan-*.md`). Guardrail:
read-only w.r.t. the *followed* pane (never sends keystrokes); it MAY
author/create tasks in *its own* pane, so running `/aitask-explore` is
guardrail-safe.

Exploration findings (confirmed against source):
- **No existing error/retry detection to reuse.** `monitor/prompt_patterns.py`
  matches only *awaiting-input* prompts (no error/traceback/retry regexes); its
  `PaneSnapshot` carries no error field. So this flow does its **own** text
  analysis of the captured screen.
- **Concern-block machinery already exists** (t1037). The
  `===AITASK-CONCERNS===` ... `===END-CONCERNS===` format
  (`aidocs/framework/shadow_concern_format.md`) is already emitted by
  `plan-challenge.md` and parsed by `.aitask-scripts/monitor/concern_parser.py`
  + consumed by the minimonitor concern picker. Capability A emits the same block
  to "mark" the errors — **no minimonitor / parser changes needed**.
- Related but distinct: `t1017` (shadow steerability). Not folded; cross-reference
  only. A's "spin a concern into its own fix-task" is complementary.

## Key files to modify

- **NEW** `.claude/skills/aitask-shadow/plan-diagnose-errors.md` — the
  sub-procedure (model its structure on `plan-challenge.md`: header + Inputs +
  advisory-only note + numbered methodology + concern-block output rules).
- `.claude/skills/aitask-shadow/SKILL.md` — add ONE Step 3 routing entry under
  "Structured analyses (read and follow the sub-procedure file)", e.g.
  "Diagnose skill/helper errors in the followed agent (`InputValidationError`,
  tracebacks, retry loops) -> read and follow `plan-diagnose-errors.md`."
  **No Step 1 proactive trigger** (see AC revision — on-request only).
  Do NOT hardcode the capability in the Step 0 greeting — it derives from Step 3
  automatically (single source of truth; a maintainer note in SKILL.md forbids a
  second copy).

## Reference files for patterns

- `.claude/skills/aitask-shadow/plan-challenge.md` — the canonical concern-block
  producer; copy its `===AITASK-CONCERNS===` fenced-format rules verbatim
  (leading `- ` mandatory, `[priority | region] body`, closing fence required,
  one logical line per concern, emit only when >=1 concern).
- `.claude/skills/aitask-shadow/plan-explain.md` — simplest sub-procedure shape.
- `aidocs/framework/shadow_concern_format.md` — single source of truth for the
  format + parser contract (capture-join, multi-block-last-wins, trigger vs
  action strictness).
- `aidocs/framework/shadow_agent.md` — pipeline overview (also UPDATE its Step 3
  capability list + sub-procedure bullets to include the new one).

## Implementation plan

1. Author `plan-diagnose-errors.md`. Methodology (numbered):
   (a) Read the captured screen (shadow Step 1; refetch if stale).
   (b) Scan for error/retry signals: `InputValidationError`, `Tool error:`,
       `Traceback (most recent call last):`, bash `error:` / stderr lines, and
       **repeated identical commands** (retry loops).
   (c) Attribute each error to the likely skill/helper it came from (which
       workflow skill or `aitask_*.sh` helper the followed agent was running, and
       the wrong-parameter vs bug-in-script distinction where inferable).
   (d) Present the candidate concerns (human-readable list) and emit the marked
       concern block (one concern per error cluster) per the
       `shadow_concern_format.md` rules. If no signal is found, say so and stop.
   (e) Let the user choose which concerns (if any) warrant a fix-task
       (AskUserQuestion, multiSelect, incl. a "none" path). For each chosen one,
       OFFER to launch `/aitask-explore` seeded with a prompt naming that
       concern's skill/helper path(s) + the captured error excerpt; only on
       explicit confirm, in the shadow's OWN pane. v1: `/aitask-explore` seed only
       (no batch-creation branch). Never auto-launch; never drive the followed pane.
2. Add the Step 3 routing entry to `SKILL.md` (no Step 1 trigger).
3. Update `aidocs/framework/shadow_agent.md` with ONE capability-level bullet (no
   signal-list duplication).

## Verification steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes (static skill — trivial pass,
  but confirms no surface breakage).
- Grep-confirm the greeting still derives from Step 3 (no hardcoded capability
  list); the new routing line is present and well-formed.
- Behavioral — positive fixture (manual): feed `aitask_shadow_capture.sh -` a
  fixture screen containing an `InputValidationError` / traceback / retry loop and
  confirm the shadow emits a valid concern block (round-trips through
  `concern_parser.py`), lets the user pick which concerns to act on, and offers
  explore-to-fix without driving the followed pane.
- Behavioral — negative-control fixture (manual): feed ≥1 fixture with benign
  error-shaped text (a passing run that prints `error:`, an intentionally failing
  test, a pasted traceback excerpt being discussed) and confirm the shadow emits
  **no** concern block — guards the false-positive surface.
