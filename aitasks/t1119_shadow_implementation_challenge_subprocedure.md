---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-07-05 08:25
updated_at: 2026-07-05 09:18
---

Add a new sub-procedure to the `aitask-shadow` skill that performs an
**adversarial review of the implementation** (the code actually written for a
task), complementing the existing adversarial review of the *plan*
(`plan-challenge.md`). It emits concerns in the same machine-parseable
`===AITASK-CONCERNS===` format so minimonitor's existing concern picker forwards
them unchanged — no parser or minimonitor changes required.

Scope note: this is a **framework-source change** implemented in the aitasks
repo. The shadow skill, its sub-procedures, `concern_parser.py`, and minimonitor
all live in the framework and are synced *downstream* into consumers (e.g.
thinking_app) via `ait: Update aitasks framework` commits — so editing only a
consumer would be overwritten. This task lands upstream and ships to all installs.

## Goal

New sub-procedure `.claude/skills/aitask-shadow/impl-challenge.md`, modeled
directly on `plan-challenge.md`, routed as a new capability. The shadow agent
stays **advisory-only** (never drives the followed pane).

## Inputs the review consumes

1. **Task definition + plan** — via `aitask_shadow_context.sh <task_id>`
   (`TASK_FILE:` + active `PLAN_FILE:` in `aiplans/`). This is "what was supposed
   to be implemented."
2. **The actual code changes (real diff)** — discover the task's commits via
   `aitask_revert_analyze.sh --task-commits <id>` (matches `(tN)` /
   `(tN_M)` in commit subjects), then read the diff of those commits (and/or the
   working tree) to review what was actually done. Advisory-only refers to the
   *followed pane*; reading local git state is fine.
3. **The plan's `## Final Implementation Notes`** — the agent's own narrative
   (bullets: *Deviations from plan*, *Issues encountered*, *Key decisions*),
   written by task-workflow Step 8 at end of implementation.

## "Too early to review" gate (required)

If the read plan does **not** contain a `## Final Implementation Notes` section,
the implementation phase of the task workflow has not completed. The procedure
must **warn the user** that it is probably too early to review the implementation
(the task workflow was not yet finished) before doing anything else — and let the
user decide whether to abort or proceed anyway with the partial state.

## Review focus (what to flag / what NOT to flag)

Focus the adversarial pass on:
- **Possible flaws in the implementation** — bugs, missed cases, incorrect logic,
  regressions in the code as actually written (checked against the plan/task
  intent and the real diff).
- **Risks left unmitigated** — do NOT re-flag risks the implementation explicitly
  addressed/mitigated; surface only risks that remain open.
- **Deviations from the plan that were not justified** — compare the diff against
  the plan; a deviation the Final Implementation Notes justify is fine, an
  unexplained/unjustified deviation is a concern.

Keep the honesty rule from `plan-challenge.md`: a short list of real problems
beats a long list of weak ones; if a dimension is genuinely clean, say so.

## Output format (reuse existing machinery)

After the human-readable prioritized list, emit the **same fenced block** as
`plan-challenge.md`:

```
===AITASK-CONCERNS===
- [priority | region] body
===END-CONCERNS===
```

- `priority` ∈ {high, medium, low}; leading `- ` mandatory (wrap-collision
  guard); one concern per logical line (soft-wrap only, no literal mid-concern
  newline); always emit the closing fence; omit the whole block if there are no
  concerns.
- `region` for implementation concerns should identify the code locus
  (e.g. `path/to/file.ext:LINE`) or the axis (`unmitigated risk`,
  `unjustified deviation`, `correctness`). Body carries full framing (problem +
  why it bites + enough context for the receiving agent to choose how to fix).
- This reuses `concern_parser.py` (`parse_concerns` / `has_concern_block`) and
  minimonitor's picker verbatim.

## Registration

Add one bullet under `SKILL.md` Step 3 "Structured analyses" pointing to
`impl-challenge.md` (e.g. trigger phrases: "review the implementation", "did it
actually do what the plan said", "check the code that was written"). The Step 0
greeting is auto-derived from Step 3 — do not hardcode.

## Concern-format single-source-of-truth doc (portability fix)

The format's cited SoT `aidocs/framework/shadow_concern_format.md` **exists
upstream but is not distributed to installs** (framework sync copies
`.claude/skills/` and `.aitask-scripts/` but not `aidocs/framework/`), so all 5
in-repo references dangle in every install. As part of this task:
- Relocate/author the concern-format doc **inside the shadow skill directory**
  (e.g. `.claude/skills/aitask-shadow/concern-format.md`) so it travels with the
  skill to every install (portable).
- Repoint the references to the skill-local path: `plan-challenge.md`,
  `plan-assumptions.md`, `plan-diagnose-errors.md`, the new `impl-challenge.md`,
  `.aitask-scripts/aitask_shadow_capture.sh`, and
  `.aitask-scripts/monitor/concern_parser.py`.
- Decide the fate of the upstream `aidocs/framework/shadow_concern_format.md`
  (keep as a thin pointer to the skill-local doc, or remove) during planning —
  investigate first whether anything else (docs site, tests) depends on the
  aidocs path before removing.

## Implementation notes / constraints

- Sub-procedure `.md` files live **only** under `.claude/skills/aitask-shadow/`
  (the `.opencode`/`.agents` trees carry only `SKILL.md`). Mirror
  `plan-challenge.md`'s placement — do not fork the file into other agent trees.
- Use the deep capture (`aitask_shadow_capture.sh --deep`) when reading long
  content off the followed pane, matching the other plan-review sub-procedures.
- No changes to `concern_parser.py` logic or minimonitor are expected (format is
  unchanged) — only the doc-reference comment updates above.

## Verification

- `tests/test_concern_parser.py` already covers the shared format; no new parser
  behavior. Consider a follow-up **manual-verification** task (cf.
  `t1053`) for a live `impl-challenge` run: launch a completed task's agent,
  invoke the implementation review, confirm the emitted block parses and
  forwards via minimonitor's 'c' picker, and confirm the shadow stayed
  advisory-only.
