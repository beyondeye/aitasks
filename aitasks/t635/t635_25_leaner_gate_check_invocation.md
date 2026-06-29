---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-06-29 09:21
updated_at: 2026-06-29 09:21
---

## Context

t635_14 unified profile→gate-declaration (the `risk_evaluation` Jinja toggle was
retired in favour of a `default_gates` profile key + runtime resolution). It
works, but it traded away some of the leanness the profile/template-render system
was built for: render-time `{% if %}` gates omit a block entirely for profiles
that don't use it, whereas t635_14's risk-gating is now **runtime checks present
in every rendered profile** (e.g. `default`'s rendered `SKILL.md` grew ~717→766
lines for content it previously rendered nothing for).

The agent-error risk is already mitigated (the decisions are tested helpers, not
prose conditionals). What remains suboptimal is the **call shape** of the gate
check/invocation: the sites mix three interaction styles, and the worst make the
agent parse text or run inline multi-command bash:

- **Producer trigger** (`planning.md` §6.1 end-of-planning terminal step):
  `aitask_gate.sh effective-gates <id> --profile <f>` emits a **list**, then the
  prose says "if the output contains `risk_evaluated`…" → the agent must
  grep/substring-scan multi-line text. (Same shape in the risk-section guard.)
- **Step-7 backfill** (`SKILL.md`): a ~6-line **inline bash block**
  (`has-gates-field` + `effective-gates | paste -sd,` + non-empty test +
  `aitask_update.sh --gates` + `./ait git` commit). This also **violates the
  repo's "encapsulate workflow bash in a whitelisted helper, don't inline it"
  convention** ([[feedback_encapsulate_workflow_bash_in_helper_script]]).
- **Self-record guard** (`SKILL.md` Step 7): `aitask_gate.sh should-self-record
  <id> <gate>` → exit code (the right shape) — but it `delegate_python`s, so it
  conflates "skip" with "python unavailable" (both exit 1).

This task optimizes the gate-check **invocation** so calls are concise,
unambiguous, and need no per-site parsing wrapper.

## Goal

Make every gate check/invocation in the task-workflow a single call the agent
either branches on by exit code or runs-and-forgets — no text grepping, no inline
multi-command bash, no per-call parsing instructions.

## Scope (the optimizations)

1. **Exit-code decision verb.** Add `aitask_gate.sh active <id> <gate> [--profile
   <f>]` → exit 0 = effectively active (task `gates:` if present else profile
   `default_gates`) / 1 = not. Replace the `effective-gates | grep` producer-trigger
   in `planning.md` and the risk-section-guard check with it:
   `aitask_gate.sh active <id> risk_evaluated && <run producer>`. Keep
   `effective-gates`/`list` for introspection/debug only.
2. **Single action verb for the backfill.** Add `aitask_gate.sh
   backfill-declaration <id> [--profile <f>]` that internally does the
   presence-check (`has-gates-field`) + resolve (`effective_gates`) + write
   (`aitask_update.sh --gates`) + path-scoped commit, printing ONE status line
   (`BACKFILLED:<csv>` / `NOOP:already-declared` / `NOOP:opt-out` /
   `NOOP:no-defaults`). Replace the Step-7 inline bash block with the single call
   (honors the encapsulate-bash convention; unit-test it).
3. **Pure-bash decision verbs (no python-availability ambiguity).** Implement the
   decision verbs (`active`, `has-gates-field`, `should-self-record`) on the
   bash/awk path (reuse `read_yaml_list`, as `cmd_list` already does) so they are
   always available → clean 0/1 with no degradation branch in the markdown.
   **Open sub-decision:** pure 0/1, OR reserve exit 2 for "couldn't determine" so
   an infra failure never silently reads as "not gated" (unambiguous vs minimal —
   decide in planning).
4. **Document the gate-CLI contract once.** A short reference (extend
   `gate-recording.md` or a new `gate-cli.md`): decision verbs → exit codes;
   action verbs → do-and-print-one-status-line. Reference it from the call sites
   instead of re-explaining parsing at each.

## Open decision (resolve during planning) — #5 self-gating procedures

The leanest option: have the workflow invoke the producer / post-approval risk
recording **unconditionally** (a one-line procedure pointer), and make each
procedure's FIRST line the exit-code gate-check that returns early if not
applicable (`aitask_gate.sh active <id> risk_evaluated || return`). This removes
gate-branching from the rendered skill entirely (closest to render-time leanness),
but the gate-check becomes less visible in the main flow. Trade-off call — present
both in the plan and let the user choose.

Also consider (may fold in or defer): moving the **backfill earlier to Step 4**
(pre-plan-mode ownership) so the task's `gates:` is canonical before planning and
every downstream site is a plain task-state read with no `--profile` fallback.
Watch: Step 4 runs for manual_verification tasks and re-entry too — guard
accordingly.

## Key files to modify

- `.aitask-scripts/aitask_gate.sh` — new `active` / `backfill-declaration`
  subcommands + dispatch + help; move decision verbs to the bash path.
- `.aitask-scripts/lib/gate_ledger.py` — keep `effective_gates` /
  `should_self_record` / `_frontmatter_has_key` as the python fallback; ensure the
  bash path mirrors them.
- `.claude/skills/task-workflow/planning.md` — producer trigger + risk-section
  guard → `active`.
- `.claude/skills/task-workflow/SKILL.md` — Step-7 backfill → `backfill-declaration`;
  self-record guard unchanged in shape (already exit-code).
- (if #5) `.claude/skills/task-workflow/risk-evaluation.md` + `gate-recording.md`
  — self-gating first line; main-flow sites become one-line pointers.
- Regenerate task-workflow goldens + committed `remote` prerenders; run
  `aitask_skill_verify.sh`.

## Reference patterns

- `cmd_list` in `aitask_gate.sh` — the bash `read_yaml_list`/awk path for the
  pure-bash verbs (#3).
- `should-self-record` (t635_14) — the exit-code decision-verb pattern to mirror
  for `active`.
- `tests/test_gate_effective_gates.sh` / `tests/test_gate_declaration_backfill.sh`
  — scaffolds for the new verb tests (real `aitask_gate.sh` entry point, fixture
  cwd + `TASK_DIR`).
- `task-creation-batch.md` `--gates` injection — the creation-side declaration.

## Out of scope / coordination

- **Step-9 gate-RUN dispatch extraction** (the ~40-line inline `ait gates run` +
  status-handling block in `SKILL.md` Step 9, from t635_12) is NOT in scope here —
  it folds into **t635_24**, which already rewrites that block to remove the legacy
  inline `verify_build` fallback. Coordinate: extend t635_24 to extract the
  gate-run glue into a procedure at the same time. (Reverse-linked from t635_24.)
- Builds on **t635_14** (DONE): the helpers (`effective-gates` / `has-gates-field`
  / `should-self-record`) and the inline glue this task refines. See
  `aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md` and
  [[feedback_negative_control_for_structural_guards]] for the test shape.
- No blocking dependency — all prerequisites are landed; pickable immediately.

## Verification

- Unit tests for `active` (effective-set membership: task-declared, profile-default,
  opt-out `[]`, absent+no-profile, missing-profile) and `backfill-declaration`
  (backfills absent, preserves `[]`, no-op already-declared / no-defaults) —
  mirror the t635_14 gate tests; exercise the real `aitask_gate.sh` entry point.
- Render-content assertions in `tests/test_skill_render_task_workflow.sh` updated:
  the producer trigger uses `active`, Step-7 uses `backfill-declaration` (no inline
  bash block remains).
- `shellcheck` clean (SC1091 baseline only); `aitask_skill_verify.sh` OK; goldens
  + committed prerenders regenerated in the same commit.
- Confirm the `default`-profile rendered `SKILL.md`/`planning.md` shrink materially
  vs the post-t635_14 baseline (the leanness this task restores).

## Step 9 (Post-Implementation)

Standard cleanup / archival / merge per task-workflow Step 9.
