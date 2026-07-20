---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [codexcli, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1180, 1181]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 09:50
updated_at: 2026-07-20 12:20
boardidx: 40
---

## Background

When spawning a Codex code agent for a skill launch, the framework currently
injects a leading `/plan ` line so Codex starts in plan mode. This was a
workaround for a Codex limitation: `request_user_input` / AskUserQuestion was
not available outside plan mode.

**That limitation no longer applies** — `ait setup` enables the
`default_mode_request_user_input` feature flag in `.codex/config.toml`, so
interactive prompts work in Codex's default mode.

Meanwhile, forcing plan mode causes its own problems — notably **dynamic skill
rendering does not work** in plan mode (the render step needs write access,
which plan mode restricts).

**Verified during planning (2026-07-20):** the Codex skill stubs (e.g.
`.agents/skills/aitask-pick/SKILL.md`) run
`aitask_skill_render.sh … --agent codex` as their step 2, which reaches
`lib/skill_template.py:246-250` `_atomic_write()` — `mkdir(parents=True)` →
`write_text()` → `os.replace()`. Three filesystem mutations, all blocked by a
read-only plan mode; the stub's step 3 then reads a rendered-variant path that
may not exist. The stated cause holds up and is no longer an assumption.

**Decision: stop injecting the `/plan` line when spawning Codex agents.**
All Codex skill launches should use the plain, already-existing default-mode
invocation path.

## Exploration findings — blast radius

The injection is fully localized to three source files plus their tests/docs.

### Policy

- `.aitask-scripts/lib/codex_plan_policy.sh` — defines
  `codex_skill_forces_plan_mode()`, which returns 0 (force plan mode) for every
  skill except the relaxed set `qa|explain|shadow|learn`. Single source of truth
  shared by the two call sites below. With plan mode gone, this function has no
  remaining true branch and the file becomes dead.

### Call sites (both already have a working default-mode `else` branch)

- `.aitask-scripts/aitask_codeagent.sh` (~line 510-525, `codex)` case): builds
  the `$aitask-*` composer prompt, then branches:
  ```bash
  if codex_skill_forces_plan_mode "$operation"; then
      CMD=("python3" "$SCRIPT_DIR/aitask_codex_plan_invoke.py" "--prompt" "$prompt" "--" "$binary" "$model_flag" "$cli_id")
  else
      CMD=("$binary" "$model_flag" "$cli_id" "$prompt")
  fi
  ```
  Removal collapses this to always taking the `else` branch.

- `.aitask-scripts/aitask_skillrun.sh` (~line 237-247, `codex)` case): the same
  branch, using `require_ait_python`. Same collapse.

### Dead helper

- `.aitask-scripts/aitask_codex_plan_invoke.py` (301 lines) — a PTY wrapper
  whose only job is to spawn Codex, wait for composer readiness (matching
  `_DEFAULT_READY_PATTERNS`), then write `/plan <prompt>\r` into the child fd
  and relay I/O until exit. Once no call site invokes it, the whole file is
  dead and should be deleted.

- **`pexpect` dependency:** `aitask_setup.sh:29` (`AIT_PIP_SPECS_COMMON`) and
  `:31` (`AIT_IMPORTS_COMMON`) list `pexpect`. A repo-wide grep shows the plan
  helper is its **only non-test consumer** — verify this again at implementation
  time before dropping it from the dependency list (removing an installed dep is
  user-visible; confirm nothing else, including future/in-flight work, imports
  it).

### Test fallout

- `tests/test_codeagent.sh` — line 38/42/44 copy the helper + policy lib into
  the fixture; line 78 py_compiles the helper; lines 175/185 assert `pick` and
  `explore` dry-runs **use** the helper; lines 191/197/205/210 assert
  `explain`/`qa`/`raw`/`batch-review` bypass it. The positive assertions must
  invert to "no codex launch uses the plan helper"; keeping negative controls for
  every operation is the right shape (see the negative-control convention).
- `tests/test_skillrun_codex_planmode.sh` (68 lines) — the whole file exists to
  test this branch; either delete it or repurpose it into a guard that asserts
  no codex skillrun path ever emits `/plan` or the helper path.
- `tests/test_codex_plan_invoke.py` (145 lines) — tests the helper directly;
  delete with the helper.
- `tests/test_shadow_spawn_learner.sh` (lines 57, 79-83) and
  `tests/test_shadow_spawn_config.sh` (lines 50-53, 67-71) — currently assert
  the relaxed skills (`shadow`, `learn`) do NOT force plan mode *while `pick`
  still does*. The `pick`-still-forces assertions must be updated; the "does not
  use the helper" assertions stay valid and become universal.

### Documentation

- `website/content/docs/installation/known-issues.md:25` — the blockquote
  stating `ait codeagent invoke` launches the planning skills (`pick`, `explore`)
  through plan mode while analysis skills run in default mode. Must be removed
  or rewritten per the current-state-only doc rule.
- `website/content/docs/installation/known-issues.md:31` — mentions Codex asking
  whether to override the current plan-mode effort setting when changing effort;
  re-check whether this still applies once launches are default-mode.
- `website/content/docs/skills/_index.md:14` already describes the
  `default_mode_request_user_input` setup step correctly — verify it needs no
  change.

## Acceptance criteria

1. No Codex skill launch path injects `/plan` — `ait codeagent invoke <op>` and
   `ait skillrun` dry-runs for **every** operation (`pick`, `explore`, `qa`,
   `explain`, `shadow`, `learn`, `raw`, `batch-review`) emit a plain
   `<binary> <model_flag> <cli_id> "<prompt>"` command with no helper and no
   `/plan` substring.
2. `aitask_codex_plan_invoke.py`, `lib/codex_plan_policy.sh`, and their
   dedicated tests are deleted; no dangling `source`/reference remains
   (grep for `codex_plan_policy`, `codex_plan_invoke`,
   `codex_skill_forces_plan_mode` returns nothing outside history).
3. A guard test asserts no codex launch path can reintroduce the injection
   (negative control at the real dry-run surface, not just a unit helper).
4. `pexpect` is dropped from `aitask_setup.sh` deps **only if** re-verified as
   having no other consumer; otherwise left in place with a note.
5. `known-issues.md` reflects the current state — no stale plan-mode prose.
6. `shellcheck .aitask-scripts/aitask_*.sh` passes; the affected test files pass.

## Notes

- Verify the claim "dynamic skill rendering does not work in plan mode" against
  the actual render path (`aitask_skill_render.sh`) during planning, so the
  motivation recorded here is accurate rather than assumed.
- Check whether any other agent tree (`.agents/`, `.opencode/`) or a seed
  template references the plan-mode launch before finishing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-20T07:55:59Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-20T09:12:17Z status=pass attempt=1 type=human
