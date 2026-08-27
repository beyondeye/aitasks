---
Task: t1569_4_task_workflow_parallel_admission_preflight.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_4 — `task-workflow` parallel-admission preflight

Consumer #1 of the shared checker: the **required** one. Parallel with t1569_5.

## Why a procedure and not a gate

`MANUAL_VERIFICATION_REACHABLE_GATES` in `lib/task_utils.sh` is an allowlist and
`filter_gates_for_issue_type()` would silently strip a new gate. The precedent is
plan-verification staleness — a step in `planning.md`, not a gate — and the
structural twin is `remote-drift-check.md`, which this mirrors. Recorded in
`aidocs/framework/manual_verification_staleness.md` ("Why not a gate").

## Step 1 — Write `parallel-admission.md`

New file `.claude/skills/task-workflow/parallel-admission.md`, shaped like
`remote-drift-check.md`: an input-context table, the invocation, output parsing,
and a disposition per verdict.

**Invocation:**

```bash
./.aitask-scripts/aitask_parallel_admission.sh check \
  --candidate <task_id> --from plan --plan <plan_file> \
  --lock-freshness require-fresh
```

- `--lock-freshness require-fresh` is not optional here. A cached lock ref hides
  a lock another agent took seconds ago — a false CLEAR at exactly the admission
  point this exists to defend.
- The checker excludes the candidate itself (t1569_3 Step 4). This procedure
  states *why* so a future reader does not "simplify" it away: `task-workflow`
  set the task `Implementing` and locked it back at **Step 4**, long before the
  plan existed.
- Re-read **live** state at call time. Never reuse a roadmap snapshot.

**Dispositions:**

| verdict | disposition |
|---|---|
| `CLEAR` | proceed, worded **"no known conflict at check time"** — never "safe to run in parallel" |
| `CLEAR_CAVEATED` | under `block`: `AskUserQuestion` confirmation naming the unverified source. Under `warn`: a visible note. **Rendered distinctly from CLEAR in both modes.** |
| `CONFLICT` | **stop-and-replan by default**, naming the overlapping task(s) and file(s); explicit user override is the alternative |
| `UNCHECKABLE` | **explicit user confirmation**, naming *why* the evidence was insufficient. Never auto-proceed. |

**State the residual race in the procedure text**: this check is a snapshot and
reserves nothing, so overlapping work can begin immediately after it passes.

**Operator recovery path, printed with every UNCHECKABLE**, keyed to the named
`UNCHECKABLE_CAUSE:`:

| cause | remedy |
|---|---|
| `inflight:<ref>\|no_plan_file` | plan it, or `ait lock --unlock <id>`, or override for that task |
| `inflight:<ref>\|all_phantom` | that plan is stale — refresh or release it |
| `locks\|unavailable` | check the network, or re-run |
| `candidate\|<reason>` | the candidate's own plan declares no resolvable surface — add concrete paths to the plan |

A prompt with no remedy is what trains users to dismiss a guard.

## Step 2 — Wire the two call sites

Order is load-bearing: the drift check can pull the base branch, which changes
what is in flight. The preflight runs **after** it, never before.

1. **`planning.md` Checkpoint** — in the "Start implementation" branch, after the
   Remote Drift Check Procedure returns "Continue anyway" and before proceeding
   to Step 7. Also in the profile-driven `start_implementation` branch, which has
   its own drift-check call.
2. **`SKILL.md` Re-entry Routing, `IMPLEMENT` route** — after its Remote Drift
   Check, before the deferred worktree fork and implementation. The world may
   have changed since the plan was approved; this is why the check re-runs.

Do **not** add it to the `POSTIMPL` route: the code is already committed there
and the only actionable branch would revert reviewed work to `Ready`.

## Step 3 — Profile knob

`parallel_admission: block | warn | off` in
`aitasks/metadata/profiles/{default,fast,remote}.yaml` and the `seed/` mirrors,
modelled on `remote_drift_check: warn|strong-only`. Document it in `profiles.md`.

**CONFLICT's disposition is stop-and-replan in both `block` and `warn`.** That is
the design and it does not change. The knob governs the hard stop on the
*non*-CONFLICT verdicts.

**Deviation, deliberate and evidence-backed:** the knob **ships defaulting to
`warn`**, not `block`. The measured projection against today's in-flight
population is UNCHECKABLE on **100% of picks** — 2 of the 4 non-candidate
`Implementing` tasks have no plan at all and t259's plan is all-phantom. Shipping
`block` immediately would prompt on every pick and train the user to dismiss the
guard.

Promoting the default to `block` is a **separate, explicitly gated step**, its
entry criterion being t1569_3's measured UNCHECKABLE and false-CONFLICT rates
falling to an agreed level. In `warn`, UNCHECKABLE still prompts for explicit
confirmation — only the hard stop is deferred. Record this in the task's Final
Implementation Notes so the deviation is not mistaken for an oversight.

## Step 4 — Renders, goldens, whitelist

```bash
./.aitask-scripts/aitask_skill_rerender.sh          # or per-profile render
./.aitask-scripts/aitask_skill_verify.sh
```

Regenerate `tests/golden/procs/task-workflow/` in the **same commit** as the
procedure edit.

**No Codex / OpenCode port task.** `parallel-admission.md` is shared-closure
content with no `{% if agent %}` gates, and Claude is the single source
(`SOURCE_AGENT_ROOT = ".claude/skills"` in `lib/skill_template.py`), so
`.agents/skills/task-workflow-*-codex-/` and `.opencode/skills/task-workflow-*/`
auto-render from it — verified identical modulo digits for an existing procedure.
CLAUDE.md's port guidance targets agent-specific surfaces only.

The **helper whitelist is** an agent-specific surface and does need entries:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_parallel_admission
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_parallel_admission
```

Five touchpoints — `.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`. **Read
`aidocs/framework/aitasks_extension_points.md:286-318` and confirm the touchpoint
list before editing any of them** rather than trusting this list.

Note `discover-helpers` only finds a helper whose literal path appears in a skill
closure — so the whitelist step must come *after* the procedure references it.

## Verification

```bash
./.aitask-scripts/aitask_skill_verify.sh
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
git diff --stat tests/golden/procs/task-workflow/      # empty after regeneration
```

Required tests:

1. A bash test driving the **real** helper through a synthetic repo for each of
   CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE, asserting the procedure's
   disposition text for each.
2. **Self-exclusion end-to-end**: claim a task exactly as Step 4 does
   (`./.aitask-scripts/aitask_pick_own.sh <id> --email ...`), write a plan, then
   run the preflight and assert `CLEAR` — not a conflict with the candidate's own
   plan. This is the failure that would otherwise hit every single pick.
3. A workflow-contract test pinning that the preflight appears **after** the
   drift check at **both** call sites.
4. A test that `parallel_admission: off` makes the whole step a no-op.
5. Live CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE rates recorded in the
   Final Implementation Notes — the evidence for any later promotion to `block`.
