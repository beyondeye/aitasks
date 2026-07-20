---
Task: t1171_stop_injecting_plan_mode_for_codex_agents.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# t1171 — Stop injecting `/plan` when spawning Codex code agents

## Context

When the framework spawns a Codex CLI agent for a skill launch (`ait codeagent
invoke pick`, `ait skillrun`, minimonitor spawns), it does not launch Codex
directly. It routes through `aitask_codex_plan_invoke.py`, a PTY wrapper that
waits for Codex's composer to become ready and then types `/plan <skill prompt>`
into it, forcing the session into Codex's plan mode.

That existed to work around a Codex limitation: `request_user_input` (the
AskUserQuestion equivalent) was unavailable outside plan mode. **That limitation
is gone** — `ait setup` now enables the `default_mode_request_user_input`
feature flag in `.codex/config.toml`, so interactive prompts work in Codex's
default mode.

Meanwhile forcing plan mode actively breaks things. **Verified during planning:**
the Codex skill stubs (e.g. `.agents/skills/aitask-pick/SKILL.md`) have a step 2
that runs `aitask_skill_render.sh … --agent codex`, and that path reaches
`lib/skill_template.py:246-250` `_atomic_write()`, which does `mkdir(parents=True)`
→ `write_text()` → `os.replace()`. Three filesystem mutations. Plan mode is
read-only, so the render is blocked and step 3 then reads a rendered variant path
that may not exist. The stated motivation holds up.

**Outcome:** every Codex skill launch uses the plain default-mode invocation.
The plan-mode machinery is deleted, not left as dead code.

## Approach

Both call sites already contain a working default-mode `else` branch — the one
`qa`, `explain`, `shadow`, and `learn` take today. So this is not new code: it is
deleting the policy function and collapsing each `if/else` to its existing `else`.
That is why confidence is high and the change is mostly subtraction.

## Steps

### 1. Collapse the two call sites

**`.aitask-scripts/aitask_codeagent.sh`**
- Delete the `source` of the policy lib (lines 19-20).
- In the `codex)` → `*)` skill branch (~505-527): delete the
  `if codex_skill_forces_plan_mode …` / `else` / `fi` wrapper, keeping only
  `CMD=("$binary" "$model_flag" "$cli_id" "$prompt")`.
- Rewrite the comment at ~509-512 (it currently explains the plan-mode split) to
  describe the single default-mode launch.

**`.aitask-scripts/aitask_skillrun.sh`**
- Delete the `source` of the policy lib (lines 34-35).
- In the `codex)` case (~239-246): same collapse, keeping
  `CMD=("$binary" "$model_flag" "$cli_id" "$codex_prompt")`. The `require_ait_python`
  call in the deleted branch goes with it — confirm `$PYTHON` is not used later in
  the file before removing.
- Update the header doc comment at **line 19**, which documents the codex launch
  shape as `python3 aitask_codex_plan_invoke.py --prompt … -- codex -m <cli_id>`.
  It becomes `exec codex -m <cli_id> "$<full_skill> --profile <profile> <args>"`,
  matching the claudecode/opencode lines above it.

### 2. Delete the dead machinery

- `.aitask-scripts/aitask_codex_plan_invoke.py` (301 lines)
- `.aitask-scripts/lib/codex_plan_policy.sh` (26 lines)

These carry four env-var overrides (`AITASK_CODEX_PLAN_PRE_SPAWN_DELAY`,
`_STARTUP_DELAY`, `_READY_TIMEOUT`, `_READY_PATTERN`) that are defined and read
only inside the helper — nothing external sets them, so they need no deprecation
path.

### 3. Drop the `pexpect` dependency

Confirmed: the helper is the **only** non-test consumer. Remove from
`.aitask-scripts/aitask_setup.sh`:
- line 29 — `'pexpect>=4.9,<5'` in `AIT_PIP_SPECS_COMMON`
- line 31 — `pexpect` in `AIT_IMPORTS_COMMON`

**Ordering constraint:** this must land in the *same commit* as the deletion of
`tests/test_codex_plan_invoke.py`. That test is the only other importer; drop the
dep while the test still exists and the setup import-check starts failing against
a test that can no longer run.

### 4. Tests

- **Delete** `tests/test_codex_plan_invoke.py` (tests the helper directly).
- **Rename/repurpose** `tests/test_skillrun_codex_planmode.sh` →
  `tests/test_skillrun_codex.sh`. Do **not** simply delete it: its `qa`/`explain`/
  `shadow` blocks assert genuinely useful non-plan behavior (prompt content,
  `%7` pane-id and `100_2` task-id forwarding). Drop the `assert_not_contains_ci
  … "aitask_codex_plan_invoke"` lines; flip the two `pick`/`explore` blocks
  (lines 52-58) from `assert_contains_ci … "aitask_codex_plan_invoke"` to
  asserting a direct `codex -m gpt-5.4` launch.
- **`tests/test_codeagent.sh`** — remove the fixture plumbing at lines 38, 42, 44
  and the `py_compile` assertion at line 78. Flip Test 11b (pick, ~173-181) and
  Test 11c (explore, ~183-186) to assert a direct codex launch. Tests 11c2/11d
  keep their `assert_not_contains_ci` lines — they become the negative controls.
- **`tests/test_shadow_spawn_learner.sh`** — delete the policy-lib block at 79-83.
  Keep line 57, update its stale comment at 55-56.
- **`tests/test_shadow_spawn_config.sh`** — delete the policy-lib block at 66-71.
  Keep line 53, update its stale comment at 50.

**New guard test** (satisfies AC 3): a negative control at the real dry-run
surface asserting that for **every** operation — `pick`, `explore`, `qa`,
`explain`, `shadow`, `learn`, `raw`, `batch-review` — neither
`ait codeagent invoke --dry-run` nor `aitask_skillrun.sh --dry-run` emits
`aitask_codex_plan_invoke` or a `/plan` substring. This is the structural guard
that stops the injection creeping back.

### 5. Documentation

- `website/content/docs/commands/codeagent.md:155` — the fullest description
  ("a PTY helper that types `/plan <skill prompt>` into Codex after the TUI
  starts"). Rewrite to the default-mode launch.
- `website/content/docs/installation/known-issues.md:25` — remove the blockquote
  about planning skills launching through plan mode.
- `known-issues.md:31` — re-check the "Codex also asks whether to override the
  current plan-mode effort setting" note; it likely no longer applies.
- `website/content/docs/getting-started.md:85` and
  `website/content/docs/skills/_index.md:14` — verify consistency; likely no change.
- Leave `CHANGELOG.md:507` and the v0.8.3 blog post alone (historical record).

### 6. Skill prose — OUT OF SCOPE (deferred to mitigation task)

`.claude/skills/task-workflow/agent-attribution.md:5` names Codex CLI as the
exemplar of an agent running workflow steps in read-only plan mode. That
exemplar becomes wrong after this change (the general claim stays true — Claude
Code's planning *is* read-only plan mode).

Because fixing it triggers a ~12-variant rerender plus goldens across
`.claude/`, `.agents/`, and `.opencode/`, it is **split into the confirmed
follow-up task `agent_attribution_prose_rerender`** (see Planned mitigations
below) to keep this diff scoped to the Codex launch path. Do not edit it here.

### 7. Correct the task record

The task's Background asserts the plan-mode/rendering conflict. Planning verified
it (see Context). Update the task file to record it as **verified**, citing
`lib/skill_template.py:246-250`, rather than leaving it as an assumption.

## Verification

```bash
# 1. No codex launch path injects /plan — the core acceptance check
for op in pick explore qa explain shadow learn; do
  ./.aitask-scripts/aitask_codeagent.sh invoke "$op" --dry-run --agent-string codex/gpt5_4
done | grep -E 'aitask_codex_plan_invoke|/plan' && echo "FAIL: injection present" || echo "PASS"

# 2. No dangling references
grep -rn 'codex_plan_policy\|codex_plan_invoke\|codex_skill_forces_plan_mode' \
  --include='*.sh' --include='*.py' --include='*.md' . | grep -v '\.git/\|CHANGELOG\|/blog/'
# expect: no hits

# 3. Affected tests
bash tests/test_codeagent.sh
bash tests/test_skillrun_codex.sh
bash tests/test_shadow_spawn_learner.sh
bash tests/test_shadow_spawn_config.sh
bash tests/run_all_python_tests.sh

# 4. Lint
shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_skillrun.sh \
           .aitask-scripts/aitask_setup.sh
```

**Live acceptance (manual):** spawn a real Codex agent via
`ait codeagent invoke pick` and confirm (a) it lands in default mode, not plan
mode, and (b) the stub's step-2 `aitask_skill_render.sh` call now succeeds and
writes the rendered variant — the actual behavior this task exists to restore.
The dry-run tests cannot cover this.

> Note: `.github/workflows/` contains **zero** references to `tests/`, so the
> shell tests do not run in CI. Verification here is manual and load-bearing.

## Risk

### Code-health risk: medium
- Dropping `pexpect` from `AIT_PIP_SPECS_COMMON` / `AIT_IMPORTS_COMMON` changes
  what `ait setup` installs and import-checks — user-visible, and wrong ordering
  breaks the setup check against a deleted test · severity: medium · → mitigation: handled in-plan (step 3 ordering constraint; verified sole-consumer via full-repo grep)
- Deleting `tests/test_skillrun_codex_planmode.sh` outright would silently drop
  unrelated coverage (shadow pane-id / task-id forwarding) · severity: medium · → mitigation: handled in-plan (step 4 renames and repurposes rather than deletes)
- Fixing the now-wrong `agent-attribution.md` exemplar rerenders ~12 skill
  variants, widening the diff beyond the Codex launch path · severity: low · → mitigation: t1181
- Shell tests are not run by CI, so a regression here is caught only by manual
  verification · severity: low · → mitigation: t1180

### Goal-achievement risk: low
- The goal is precisely "stop injecting `/plan`", and the default-mode `else`
  branch this collapses to is already exercised in production by `qa`, `explain`,
  `shadow`, and `learn` — so the target state is proven, not newly written. Both
  call sites and the full reference set were enumerated by grep during planning.
- Residual: the behavior this task exists to restore (Codex reaching default mode
  *and* the step-2 render succeeding) is not provable by dry-run tests · severity: low · → mitigation: t1180

### Planned mitigations
- timing: after | name: codex_default_mode_live_verification (created: t1180) | type: test | priority: medium | effort: low | addresses: goal-achievement residual + no-CI-coverage | desc: Manual-verification task — spawn a real Codex agent, confirm it lands in default mode and that the stub's step-2 aitask_skill_render.sh call succeeds and writes its rendered variant.
- timing: after | name: agent_attribution_prose_rerender (created: t1181) | type: documentation | priority: low | effort: low | addresses: diff-widening from the ~12-variant rerender | desc: Fix the now-wrong "(e.g., Codex CLI)" plan-mode exemplar in .claude/skills/task-workflow/agent-attribution.md:5, rerender all variants, regenerate goldens in the same commit.

## Final Implementation Notes

- **Actual work done:** Implemented steps 1-5 and 7 as planned. Both call sites
  (`aitask_codeagent.sh`, `aitask_skillrun.sh`) collapsed to the pre-existing
  default-mode `else` branch; `aitask_codex_plan_invoke.py` (301 lines) and
  `lib/codex_plan_policy.sh` deleted along with their `source` lines; `pexpect`
  dropped from both `aitask_setup.sh` arrays in the same commit as
  `tests/test_codex_plan_invoke.py`; tests updated; docs rewritten; the task's
  Background amended to record the verified motivation. Net: 12 files,
  +36 / −552, plus one new guard test.

- **Deviations from plan:**
  1. **Step 6 deliberately excluded.** The `agent-attribution.md` exemplar fix
     was split into the confirmed `agent_attribution_prose_rerender` follow-up
     (decided during risk-mitigation design, before implementation), keeping this
     diff scoped to the Codex launch path. Not a silent scope change — it is
     recorded in Planned mitigations above.
  2. **Docs: two of four files needed no change.** `getting-started.md:85` and
     `skills/_index.md:14` already described default-mode operation correctly, so
     they were left alone rather than edited for the sake of it.
  3. **`known-issues.md:31` removed rather than reworded.** The sentence's premise
     ("accept it so the planning phase runs at high effort too") is false once the
     planning phase no longer runs in Codex plan mode.

- **Issues encountered:**
  1. **The new guard test caught a flaw in itself.** Its dangling-reference check
     initially grepped `tests/` as well as `.aitask-scripts/`, so it flagged the
     *legitimate* `assert_not_contains` negative controls in `test_codeagent.sh`
     and the two shadow tests. Fixed by scoping the grep to production source,
     with a comment explaining why tests are excluded.
  2. **Guard proven falsifiable.** Rather than trust a passing guard, it was fed
     two synthetic regressions: the helper name restored, and a bare `/plan`
     token typed without the helper. Both sentinels fired independently, so
     neither is redundant.
  3. **Python suite noise required a baseline.** The suite reported failures, so a
     detached worktree at clean HEAD was used for comparison: baseline
     14 failures + 2 errors vs. 4 failures + 1 error with these changes, over an
     identical 1765 tests. Counts vary run-to-run on identical code — the suite is
     order-dependent/flaky, and this change (which edits no Python source)
     introduced nothing. Worktree removed afterward.

- **Key decisions:**
  - **Repurposed rather than deleted `test_skillrun_codex_planmode.sh`** →
    `test_skillrun_codex.sh`. Deleting it would have silently dropped unrelated
    coverage (shadow `%7` pane-id and `100_2` task-id forwarding) that had nothing
    to do with plan mode.
  - **Guard placed at the real dry-run surface** (both `codeagent invoke` and
    `skillrun`, all 8 operations) rather than unit-testing a helper, so it fails
    the way a regression would actually arrive.
  - **Two independent sentinels** in the guard (`aitask_codex_plan_invoke` and
    `/plan`), so reintroducing the injection by a different mechanism than the
    old helper is still caught.
  - **shellcheck compared against baseline** (26 → 24 findings) rather than
    reported as "clean" — the remaining findings are pre-existing
    `aitask_setup.sh` style items and SC1091 source-following notices.

- **Upstream defects identified:**
  - `tests/run_all_python_tests.sh:22-26 — runner masks failures: prints "Results: 25 passed, 0 failed" and exits 0 while the unittest phase beneath it reports FAILED (14 failures + 2 errors of 1765). A real regression in any Python test would be invisible to anyone trusting the exit code or summary line. Compounded by .github/workflows/ containing zero references to tests/, so nothing else catches it.`
  - `tests/test_agent_command_dialog_default_session.py:21 — order-dependent dual-import failure: passes in isolation, fails in the full suite with "AgentCommandScreen() is not an instance of <class 'agent_command_screen.AgentCommandScreen'>". The module is loaded under two distinct names, so isinstance identity breaks depending on which test ran first. Pre-existing; present on clean HEAD.`
