---
priority: low
effort: medium
depends: [1536]
issue_type: refactor
status: Ready
labels: [task_workflow, git, claudeskills]
gates: [risk_evaluated]
anchor: 1233
followup_kind: risk_mitigation
created_at: 2026-08-17 11:54
updated_at: 2026-08-17 11:54
---

## Origin

Risk-mitigation ("after") follow-up for t1277, created at Step 8d after
implementation landed.

## Risk addressed

Addresses: two nearly-identical branch-flag pairs left behind by the
backward-compatible surface.

From t1277's plan `## Risk` section, verbatim:

> The flag surface grows to two nearly-identical pairs
> (`--base-branch[-file]` vs the retained base-neutral
> `--output-branch-default[-file]`); a future edit that forgets the distinction
> reintroduces exactly this bug from the other side · severity: medium

## Goal

Once t1536 has landed and both `aitask_plan_externalize.sh` call-sites are
settled, decide whether `--output-branch-default` / `--output-branch-default-file`
can be deleted, and migrate their test cases onto `--base-branch[-file]`.

`.aitask-scripts/aitask_plan_externalize.sh` now carries **two** flag pairs that
resolve almost the same value:

- `--base-branch <b>` / `--base-branch-file <path>` — the Step-5 resolved base
  branch. Recorded as the plan header's `Base branch:` **and** used as the
  last-resort merge target. This is what the workflow passes (see
  `plan-externalization.md`'s `<branch-flags>` contract).
- `--output-branch-default <b>` / `--output-branch-default-file <path>` — a
  **base-neutral** merge-target default: it sets `Output branch:` only and
  deliberately leaves `Base branch:` alone.

t1277 kept the legacy pair deliberately (user decision at planning time): the
alternative was rewriting the ~5 existing test cases built around it, and its
base-neutrality now serves as a live negative control for the new behaviour. The
accepted cost is that a future edit which forgets which pair is which can
reintroduce t1277's bug from the other side.

## Why this is gated on t1536

`depends: [1536]` is deliberate. t1536 adds a third flag (`--worktree`) through
the same `<branch-flags>` channel and settles what each call-site passes. Deciding
the legacy pair's fate before that means deciding twice.

## Suggested direction

1. Confirm no caller (in this repo or in the seed/whitelist surfaces) still passes
   `--output-branch-default[-file]`. As of t1277 the workflow does not; grep
   `.claude/skills/`, `.agents/skills/`, `.opencode/`, and `seed/`.
2. Decide between:
   - **Delete**, migrating `tests/test_plan_externalize.sh` Tests 7h / 7l / 7m /
     7p / 7q and the relevant rows of Tests 7s / 14b / 14e onto
     `--base-branch[-file]`; or
   - **Keep and pin harder** — if a base-neutral merge-target default is judged
     genuinely useful, document the use case that needs it (there is none in-tree
     today) rather than leaving it as unexplained surface.
3. Either way, keep the negative control that distinguishes the pairs: some test
   must still prove that setting a merge-target default does not move
   `Base branch:` (today that is Test 14c's "legacy default claims output only"
   row and Test 7h's "legacy default stays base-neutral").

## Acceptance

- A decision is recorded (in the plan) with its rationale, not just an edit.
- If deleted: no flag, doc, seed, or test references remain; the full
  `tests/test_plan_externalize.sh` suite passes; `Base branch:` /
  `Output branch:` resolution is unchanged for every combination the Test 7s
  matrix and Tests 14/14b/14c/14e pin today.
- If kept: `plan-externalization.md` and the helper's usage block name a concrete
  caller or use case for the base-neutral variant.
- The base-neutrality negative control still exists and still fails when broken.
