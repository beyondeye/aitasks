# Execution Profiles

Reference documentation for execution profiles used by the task-workflow skill
and calling skills (aitask-pick, aitask-explore, etc.).

## Table of Contents

- [Profile Schema Reference](#profile-schema-reference)
- [Gate Declaration Model](#gate-declaration-model)
- [Customizing Execution Profiles](#customizing-execution-profiles)
- [Default Profile Configuration](#default-profile-configuration)
- [Profile Override Argument](#profile-override-argument)

---

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They pre-answer workflow questions to reduce interactive prompts. Two profiles ship by default:
- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use userconfig email, work locally on current branch, reuse existing plans

## Profile Schema Reference

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `name` | string | yes | Display name shown during profile selection | Step 0a |
| `description` | string | yes | Description shown below profile name during selection | Step 0a |
| `skip_task_confirmation` | bool | no | `true` = auto-confirm task; omit or `false` = ask | Step 0b |
| `default_email` | string | no | `"userconfig"` = from userconfig.yaml (falls back to first from emails.txt); `"first"` = first from emails.txt; or a literal email address; omit = ask. Note: `assigned_to` from task metadata always takes priority regardless of this setting (see Step 4 email resolution). | Step 4 |
| `create_worktree` | bool | no | `true` = create worktree; `false` = current branch | Step 5 |
| `base_branch` | string | no | Branch name (e.g., `"main"`) | Step 5 |
| `plan_preference` | string | no | `"use_current"`, `"verify"`, or `"create_new"` | Step 6.0 |
| `plan_preference_child` | string | no | Same values as `plan_preference`; overrides `plan_preference` for child tasks. Defaults to `plan_preference` if omitted | Step 6.0 |
| `plan_verification_required` | int | no | Positive integer; default `1` | Step 6.0 |
| `plan_verification_stale_after_hours` | int | no | Positive integer; default `24` | Step 6.0 |
| `post_plan_action` | string | no | `"start_implementation"` = skip to impl; `"ask"` = always show checkpoint; omit = ask | Step 6 checkpoint |
| `post_plan_action_for_child` | string | no | Same values as `post_plan_action`; overrides `post_plan_action` when the current task is a child task. Defaults to `post_plan_action` if omitted | Step 6 checkpoint |
| `record_gates` | bool | no | `true` = record approval checkpoints (plan/review/merge approval, plus build and risk evaluation when they run) as gate-run entries in the task's `## Gate Runs` ledger, committed for cross-PC visibility and later resume; omit or `false` = disabled (opt-in, off by default) | Steps 6–9 |
| `default_gates` | list | no | Comma-separated gate names declared into new tasks' `gates:` frontmatter (auto-injected as `--gates` at creation) and backfilled onto a picked task that lacks the field. Drives the planning risk producer in lockstep with the verify-time checker — declaring `risk_evaluated` is what now runs risk evaluation (it replaces the former `risk_evaluation` toggle). Omit/empty = declare nothing. See **Gate Declaration Model**. | Step 6.1 / Step 7 (creation + backfill) |
| `max_parallel_gates` | int | no | Max unlocked machine-gate verifiers the gate orchestrator (`aitask-run-gates` / `ait gates run`) dispatches concurrently, capped by core count; omit = `2` | `aitask_run_gates.sh` (gate orchestrator) |
| `enableFeedbackQuestions` | bool | no | `false` = skip satisfaction feedback prompts; omit or `true` = ask them | Satisfaction Feedback Procedure |
| `qa_mode` | string | no | `"ask"` = prompt; `"create_task"` = auto-create follow-up; `"implement"` = implement tests now; `"plan_only"` = export plan only; omit = ask | aitask-qa Step 5 |
| `qa_run_tests` | bool | no | `true` = run discovered tests; `false` = skip test execution; omit or `true` = run | aitask-qa Step 4 |
| `qa_tier` | string | no | `"quick"`, `"standard"` (default), `"exhaustive"` | aitask-qa Step 1c |
| `remote_drift_check` | string | no | `"warn"` (default — soft warning when remote is ahead with no plan-overlap, strong warning with overlap), `"skip"` (do nothing), `"strong-only"` (only prompt when overlap exists) | Step 6 checkpoint (post-plan) |
| `manual_verification_mode` | string | no | `"ask"` (default — prompt fires with autonomous / autonomous_with_plan / skip), `"manual"` (skip prompt; straight to interactive), `"autonomous"` (skip prompt; run autonomous), `"autonomous_with_plan"` (skip prompt; design + approve + execute). Controls only the up-front prompt — the per-item `auto` verb in the interactive loop is always available regardless. | Manual Verification Step 1.5 |
| `headless` | bool | no | `true` = a fully autonomous profile (no interactive prompts) used where `ait setup` never ran, e.g. Claude Code Web. Marks the profile as one whose `prerender_for_headless` skills ship committed prerenders. Currently only `remote`. | (build-time: `aitask_skill_verify.sh`) |

Only `name` and `description` are required. Omitting any other key means the corresponding question is asked interactively.

> **Committed headless prerenders (`headless` × `prerender_for_headless`):** A
> skill that declares `prerender_for_headless: true` in its `SKILL.md.j2`
> frontmatter ships a pre-rendered closure for every `headless: true` profile,
> committed to git (the `!…-<profile>-/` un-ignore entries in `.gitignore`), so
> it works in environments where `ait setup` has not rendered skills on demand.
> `aitask_skill_verify.sh` discovers these two markers and fails loudly if any
> committed prerender is missing or has drifted from its source closure — run
> `aitask_skill_rerender.sh <profile>` and commit when it does.

> **Plan verification tracking (`plan_verification_required`, `plan_verification_stale_after_hours`):** When `plan_preference` (or `plan_preference_child`) is `"verify"`, the workflow consults the plan file's `plan_verified` metadata list to decide whether a fresh verification is actually needed. `plan_verification_required` is the number of fresh (non-stale) entries required to skip re-verification — default `1` means a single prior verification is sufficient. `plan_verification_stale_after_hours` is how old (in hours) an entry may be before it no longer counts as fresh — default `24`. Both keys apply uniformly to parent and child tasks — there are no `_child` variants. The actual decision (skip / verify / ask) is computed by `./.aitask-scripts/aitask_plan_verified.sh decide`, which returns a structured report the workflow parses directly.

> **Remote-specific profile fields** (e.g., `done_task_action`, `review_action`, `issue_action`) are documented in the `aitask-pickrem` skill. They are only recognized by that skill and ignored by this workflow.

## Gate Declaration Model

Profiles declare **which gates** a task carries via `default_gates`; the gate
registry (`aitasks/metadata/gates.yaml`) defines **how** each gate runs. A
checkpoint is configured in exactly one place — never both. (This is the principle
behind retiring the former `risk_evaluation` toggle in favour of declaring the
`risk_evaluated` gate.)

- **Effective gate set.** For any task, the effective set is its own `gates:`
  frontmatter field when present (even an explicit empty `gates: []`, a deliberate
  opt-out), otherwise the active profile's `default_gates`. The workflow resolves it
  with `aitask_gate.sh effective-gates <task_id> [--profile <file>]`.
- **Declaration points.** Profile-driven task creation auto-injects `--gates` from
  `default_gates` (see `task-creation-batch.md`); when a picked task has no `gates:`
  field, the task-workflow **backfills** it from `default_gates` post-approval
  (Step 7). After that the task's literal `gates:` field is authoritative everywhere
  (planning producer, Step-9 orchestrator, archival guard).
- **Producer + checker toggle together.** Declaring `risk_evaluated` runs **both**
  the planning-time risk **producer** (the `## Risk` section + levels, before plan
  approval) and the verify-time **checker** (the `aitask-gate-risk` verifier at
  Step 9). One never runs without the other.
- **Caveat — human gates need `record_gates`.** A declared **human** gate
  (`plan_approved` / `review_approved` / `merge_approved`) is recorded only by the
  workflow (under `record_gates: true`), not by the orchestrator. Declaring one
  without `record_gates` would leave it unrecorded and **deadlock archival** (which
  requires every declared gate to pass). The shipped `fast` profile declares only
  `risk_evaluated` (a machine gate the orchestrator records), so it is unaffected —
  but custom profiles must pair any human-gate declaration with `record_gates`.
- **Registry-level `default_gates` (future).** The registry may also carry a
  top-level `default_gates` as a project-wide baseline applied when a task has no
  profile context; that fallback is **not yet implemented** — the profile key is the
  active mechanism.

## Customizing Execution Profiles

**To create a custom profile:**
1. Copy an existing profile: `cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml`
2. Edit `name` and `description` (both required — `description` is shown during profile selection)
3. Add, remove, or change setting keys as needed
4. Any key you omit will cause that question to be asked interactively

**Example — worktree-based workflow:**
```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
enableFeedbackQuestions: true
```

## Default Profile Configuration

Set a default execution profile per skill in `project_config.yaml` (team-wide) or `userconfig.yaml` (personal override):

```yaml
# project_config.yaml (shared with team)
default_profiles:
  pick: fast
  review: default

# userconfig.yaml (personal, gitignored)
default_profiles:
  pick: default   # overrides team's "fast"
```

Valid skill names: `pick`, `fold`, `review`, `pr-import`, `revert`, `explore`, `pickrem`, `pickweb`, `qa`.

Values are profile names (without `.yaml` extension) matching the `name` field in profile YAML files.

You can also set defaults via the Settings TUI (`ait settings` → Project Config tab), which renders a per-skill profile picker for `default_profiles`.

## Profile Override Argument

All skills that support profiles accept an optional `--profile <name>` argument:

```
/aitask-pick --profile fast
/aitask-pick 42 --profile fast
/aitask-fold --profile fast 106,108
/aitask-review --profile default
/aitask-pickrem 42 --profile remote
```

The argument is position-independent — it can appear anywhere in the argument string.

### Resolution Order

1. `--profile <name>` argument (highest priority)
2. `userconfig.yaml` → `default_profiles.<skill>` (personal)
3. `project_config.yaml` → `default_profiles.<skill>` (team)
4. Interactive selection / auto-select (fallback)

**Notes:**
- Profiles are partial — only include keys you want to pre-configure
- The `description` field is shown next to the profile name when selecting a profile
- Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten)
- Plan approval (ExitPlanMode) is always mandatory and cannot be skipped by profiles
- `enableFeedbackQuestions` defaults to `true` when omitted; set it to `false` for non-interactive or unattended workflows
