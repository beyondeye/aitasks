---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [shadow, skills, website, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 23:02
updated_at: 2026-10-06 07:55
completed_at: 2026-10-06 07:55
---

## Goal

Add a new shadow-agent capability, shortcode **`>pd`** (plan decisions). It turns
a review prompt the user already finds useful into a single shortcode:

> "explain the task in simple words and the design decisions incorporated in the
> plan and the probable pros and cons"

Then bring the shadow shortcode documentation up to date and make it
satisfactory (see "Docs" below).

## Why a new code (and not `>pa` or `>t`)

- **`>pa`** (`plan-assumptions.md`) lists a plan's hidden premises. It is a
  review round that produces concerns: it saves a plan snapshot, checks the
  rejection store, writes a round header, and ends with a
  `===AITASK-CONCERNS===` block for minimonitor's picker. The new ask is a
  plain-language explanation, not a list of concerns to forward.
- **`>t`** (`task-summarize.md`) is the closest neighbour: the task in plain
  words, how the agent means to get there, and how far along it is. It does not
  name the plan's design decisions or weigh their pros and cons.
- **`>px`** (`plan-explain.md`) is interactive and teaches the technical
  subjects the plan relies on. That is a different goal.

`>pd` is free: `>d`, `>pa`, `>pc`, `>ps`, `>px` are taken. It does not compose
with `>r`, because only the four concern producers (`>rpc`, `>ri`, `>rpa`, `>rd`)
compose, and `>pd` is not one. Keep the `>r` composition list unchanged.

## Shape of `>pd` (new `.claude/skills/aitask-shadow/plan-decisions.md`)

Model it on `task-summarize.md`:
- **On request only.** Never offered at startup, after a capture, or as a
  proactive offer.
- **Not a concern producer.** No concern block, no rejection store, no snapshot,
  no round header. `concern-format.md` does not apply. Of `round-preamble.md`,
  only §1 (the audience rule) and §6's plan **source selection** apply, exactly
  as `task-summarize.md` uses them.
- **Inputs.** Get the source task id via shadow Step 2, then run
  `aitask_shadow_context.sh <id>` to get `TASK_FILE:` and `PLAN_FILE:`.
  `PLAN_FILE:NOT_FOUND` falls through the §6 ladder: a single
  `~/.claude/plans/<name>.md` path on the deep capture, else the deep capture
  itself, treated as possibly partial. Say where the plan came from.
- **Output** (prose, for a non-expert reader):
  1. The task in simple words: what it achieves and why it is worth doing (a
     short version of `>t`'s first paragraphs, not a repeat of them).
  2. The **design decisions** in the plan. Each one names the choice, the
     alternatives it implicitly or explicitly rejected, and why the plan went
     this way. Ground each decision in the plan text. If the plan does not
     state a rationale, say "not stated in the plan" instead of inventing one.
  3. The **probable pros and cons** of each decision (or of the overall
     approach): what it buys, what it costs, and what to watch for.
  4. A one-line follow-up offer: `>pc` to challenge, `>pa` for assumptions,
     `>px` for a subject-by-subject walkthrough.
- No plan found → say a plan could not be found from here, give the task part
  only, and say decisions need a plan.
- Advisory-only guardrail unchanged.

## Code/skill touchpoints

- `.claude/skills/aitask-shadow/SKILL.md.j2` Step 3: add a `>pd` bullet under
  "Structured analyses" (with its natural-language triggers, e.g. "explain the
  design decisions", "pros and cons of this plan"). Step 0's greeting is derived
  from Step 3, so no separate list needs editing there.
- `.claude/skills/aitask-shadow/task-summarize.md` step 5: add `>pd` to the
  follow-up line.
- Regenerate the 3 claude goldens `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`
  (see "Regenerate goldens after any `.md.j2` or closure edit" in
  `aidocs/framework/skill_authoring_conventions.md`). Run
  `./.aitask-scripts/aitask_skill_verify.sh`.
- `tests/test_skill_render_aitask_shadow.sh` Test 2s: add `` `>pd` `` to the
  registered-codes list.
- `tests/test_shadow_phase_advisory.sh`: add `plan-decisions.md` to the
  `CAPABILITIES` array (~line 118). **Caveat (t1779):** that sweep reads
  whatever rendered closures are on disk without re-rendering them, so stale
  `-default-` closures fail it. Re-render the closures, or coordinate with
  t1779, before trusting a red result.
- Check `.aitask-scripts/monitor/` and minimonitor for any hardcoded list of
  shadow capabilities or shortcodes (none was found during exploration, but
  confirm).

## Docs

Shadow docs must be updated for `>pd`. The current website shortcode docs were
reviewed during exploration: they are **current** (every Step 3 code is
listed) but **not satisfactory**:

1. `website/content/docs/workflows/shadow-agent.md` puts all the shortcodes in a
   single ~110-word bullet ("Every capability has a shortcode", ~line 37).
   Replace it with a `| code | what it does |` table, matching the sibling
   brainstorm-discuss docs (`website/content/docs/skills/aitask-brainstorm-discuss.md`,
   `website/content/docs/tuis/brainstorm/how-to.md`). Keep the rules: `>`
   required, codes work when embedded, a mention is not an invocation, `>?`
   reprints the list, and `>r` composes only with `pc`/`i`/`pa`/`d`.
2. Most capability sections don't name their code. Add each code in its own
   section: `>e` (Explain what the agent is doing), `>q` (Help you answer a
   prompt), `>px`/`>pc`/`>ps`/`>pa` (each mode in "Interrogate a plan"), `>d`
   (Diagnose), `>l` (Learn a skill), `>r` (recheck rounds, wherever that is
   described).
3. "Two things are worth knowing:" is followed by four bullets. Fix the count,
   or drop it.
4. Add `>pd` to the page: a new mode in "Interrogate a plan" ("four distinct
   ways" → five), and an entry in the on-request-only bullet.
5. `aidocs/framework/shadow_agent.md`: add `plan-decisions.md` to the
   sub-procedure list (~line 128) and `>pd` to the shortcode list (~line 169).
6. Check `website/content/docs/concepts/shadow-agent.md` and the
   minimonitor/monitor how-to pages for any capability enumeration that needs
   `>pd`.
7. Follow `aidocs/framework/documentation_conventions.md` (current-state only).
   Run `python3 check_links.py --build` in `website/` after editing.

## Out of scope / follow-ups

- Porting to Codex CLI (`.agents/skills/aitask-shadow`) and OpenCode
  (`.opencode/skills/aitask-shadow`): create separate follow-up aitasks, per the
  CLAUDE.md skill-change rule.
- Related, not folded: t1780 (manual live verification of shadow shortcodes; it
  may want a `>pd` item added), t1779 (stale-render defect in the phase-advisory
  sweep).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T20:52:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-05T21:39:23Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-06T04:55:42Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:97999e3b85200a78

> **✅ gate:risk_evaluated** run=2026-10-06T04:55:42Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1894/risk_evaluated_2026-10-06T04:55:42Z-risk_evaluated-a1.log`
