---
Task: t1610_legacy_verify_build_exit_contract.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1610 — Teach the legacy `verify_build` prose path the gate exit contract

## Context

t1605 taught `.aitask-scripts/lib/gate_verifier_lib.sh` an **opt-in, per-key**
exit contract: for a config key listed in `project_config.yaml`'s
`gate_command_exit_contract`, that key's command exiting **2** records a gate
`skip` ("I did not run") instead of a `fail`. Any other non-zero exit is still a
fail; over a command list a fail short-circuits and a skip does not.

That contract lives entirely inside `run_command_gate`, which only the three
gate verifiers (`build_verified`, `tests_pass`, `lint`) call. The framework runs
the same commands a **second** way — as agent prose:

| path | opted-in command exits 2 |
|---|---|
| `build_verified` gate verifier | `skip` — satisfied, dependents released |
| legacy Step-9 `verify_build` prose | build failure → agent sent back to "fix the build" |
| `aitask-qa` 4b `test_command` / `lint_command` | counted as a failed component |

So a project that opts in gets two different verdicts for one command. t1605
named this in its plan's *Out of scope* and spawned this task to discharge it.

**Decision (design point 1): fix, not document.** The prose paths are taught the
contract by routing every configured-command run through **one new helper** that
reuses `run_command_gate`'s own logic, so the rule stays in a single place
instead of being restated in three skill files that will drift.

## Approach

Three layers, each with one canonical site:

1. **Rule** — extracted from `run_command_gate` into a reusable shell function in
   the same lib. Constants (`GATE_COMMAND_EXIT_CONTRACT_KEY`,
   `GATE_COMMAND_SKIP_EXIT`, `GATE_COMMAND_KEYS`) and the exit table stay where
   t1605 put them.
2. **Helper** — a new whitelisted script an agent calls; it prints a verdict and
   never touches the gate ledger.
3. **Procedure** — one shared skill procedure file that the three legacy prose
   sites reference instead of restating the run-and-branch steps.

---

### Pre-phase (risk mitigations)

1. `[pin_gate_ledger_result_strings]` **Before touching `run_command_gate`**, add
   characterization assertions to `tests/test_gate_verifiers.sh` that pin the
   appended ledger block's `result=` text for all four outcomes — `all
   <config_key> command(s) passed`, `command failed (exit <rc>): <cmd>`,
   `command reported skip (exit 2): <cmd>`, and `no <config_key> configured`.
   The suite currently pins `status=` and the verifier exit codes but not the
   result string, so extraction could silently reword the orchestrator's
   recorded history. Run the suite and confirm the new assertions **pass against
   the un-refactored code** — that is what makes them a baseline rather than a
   guess — then do the extraction and confirm they still pass.

---

## 1. `.aitask-scripts/lib/gate_verifier_lib.sh` — extract the runner

Extract the command-list execution + exit-contract resolution out of
`run_command_gate` into a new function in the same file. `_gate_config_values`
keeps its name and position (t1605's `pin_command_resolution` mitigation pins it
as "the one reader"; only its comment gains the fourth call site).

```bash
# run_project_command_key <config_key> <log_path>
# Resolves project_config.yaml <config_key>, applies the exit contract, runs the
# command(s), tees to <log_path>. Sets, and does not print:
#   PROJECT_CMD_STATUS  pass|fail|skip
#   PROJECT_CMD_CODE    0|1|2
#   PROJECT_CMD_REASON  none_configured|all_passed|command_failed|command_skipped
#   PROJECT_CMD_RESULT  one-line human text (today's `result=` string, verbatim)
#   PROJECT_CMD_NOTE    unrecognized-opt-in-key note, "" when none
```

`run_command_gate` becomes: `mkdir` the sidecar dir → call
`run_project_command_key` → `aitask_gate.sh append` with the same
`status`/`result`/`note=` fields → `return $PROJECT_CMD_CODE`. **The appended
ledger fields must be byte-identical to today's** — `tests/test_gate_verifiers.sh`
asserts on them and must pass unchanged.

The file header docblock gains a line naming its second consumer (the legacy
helper below) so the "gate verifier lib" name stays honest about its scope.

## 2. New helper `.aitask-scripts/aitask_run_project_command.sh`

Thin CLI over `run_project_command_key`. Sources `terminal_compat.sh`,
`yaml_utils.sh`, `gate_verifier_lib.sh` — the same three the gate wrappers
source (`aitask_gate_build.sh` is the model). **Appends nothing to any ledger.**

```
Usage: aitask_run_project_command.sh <config_key> [--task-id <id>] [--log <path>]
```

- `<config_key>` validated against `GATE_COMMAND_KEYS` — anything else exits 3.
- `--task-id` → log at `.aitask-gates/<id>/<config_key>_legacy_<run>.log`;
  otherwise a `mktemp` file. `--log` overrides.

stdout — `KEY:value` lines, the shape `aitask_plan_verified.sh decide` already
uses. Command output goes to the log **only**, so stdout stays a clean data
channel:

```
VERDICT:pass|fail|skip
REASON:none_configured|all_passed|command_failed|command_skipped
DETAIL:<one line>
LOG:<path>
NOTE:<text>        # only when an unrecognized opt-in key was seen
```

Exit `0`=pass `1`=fail `2`=skip `3`=usage/infra (no `VERDICT:` line printed) —
the verifier contract, so verdict codes stay disjoint from transport failures.

**Whitelist all 5 touchpoints** (`aidocs/framework/aitasks_extension_points.md`):
`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`. No `ait` dispatcher entry — nothing a human
types.

## 3. New procedure `.claude/skills/task-workflow/build-verification.md`

The single canonical prose site. Inputs `config_key` (default `verify_build`)
and optional `task_id`; returns `build_verdict` ∈ `pass|fail|skip|none` and
`build_log`.

**The invocation is given as an exact, copy-safe block — not as prose.** Exit
`1` and `2` are both *normal* outcomes here, which rules out the capture shape
Step 9 uses today for `gates_out` / `gates_rc`:

```bash
# WRONG — do not copy this shape for the helper.
bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build)"; bv_rc=$?
```

Under `set -e` those are two separate simple commands: the assignment inherits
the command substitution's status, errexit fires, and the shell exits **before**
`bv_rc=$?` ever runs. Verified — a probe of that form under `set -euo pipefail`
against a command exiting 2 terminated the script with status 2 and never
reached the next line. Step 9 gets away with it only because there every nonzero
status *is* an abort-worthy infrastructure failure; here it is the ordinary
skip, so the same shape would defeat this task's entire point precisely in
strict callers. Use the tested form — errexit is suspended inside an `if`
condition, and `$?` in the `else` branch is that condition's status:

```bash
if bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id <task_id>)"; then
  bv_rc=0
else
  bv_rc=$?
fi
bv_verdict="$(printf '%s\n' "$bv_out" | sed -n 's/^VERDICT://p')"
bv_reason="$(printf '%s\n'  "$bv_out" | sed -n 's/^REASON://p')"
bv_log="$(printf '%s\n'     "$bv_out" | sed -n 's/^LOG://p')"
```

Probed under `set -euo pipefail` across all four helper exit codes: `0→pass`,
`1→fail`, `2→skip`, `3→` empty verdict, script reaching the end in every case.

**Do not add `2>&1`** — the helper's stderr carries the human-facing warning
stream (an unrecognized `gate_command_exit_contract` entry) and merging it would
corrupt the `KEY:value` parse; the machine-readable copy of that warning arrives
on stdout as `NOTE:`. An empty `bv_verdict` is *not* a verdict — it is the
infrastructure case in step 2.

Steps:

1. Run the block above, then branch on `bv_verdict` (`bv_rc` is a cross-check,
   never the primary signal).
2. `bv_rc` = `3`, or `bv_verdict` empty → **infrastructure** failure. Diagnose;
   do not treat it as a build failure and do not "fix the code". (Same shape as
   Step 9's existing `gates_rc` nonzero branch.)
3. `pass` → proceed. `build_verdict=pass`.
4. `skip` + `none_configured` → display "No `<config_key>` configured — skipping
   build verification." `build_verdict=none`.
5. `skip` + `command_skipped` → **the command declared it did not run.** Do NOT
   go back and fix a build. Print `DETAIL` so the skip is visible in the
   transcript, then proceed. `build_verdict=skip`.
6. `fail` → today's three-way handling verbatim: read `LOG:`, diff against the
   base; task-caused → fix and re-run the helper until it passes;
   pre-existing/unrelated → log under "Build verification" in the plan's Final
   Implementation Notes and proceed. `build_verdict=fail`.
7. `NOTE:` present → surface it (a typo'd `gate_command_exit_contract` entry
   looks exactly like "not opted in" otherwise).

No Jinja — the procedure is profile-invariant. Recording stays with the caller.

## 4. Call sites — replace the restated rule with a reference

- **`.claude/skills/task-workflow/SKILL.md`** Step 9 legacy branch (≈ lines
  820–830): the five inline bullets become one reference to the procedure with
  `config_key=verify_build`. The `record_gates`-guarded recording below it stays
  in place and becomes verdict-driven: *when `build_verdict` is not `none`,*
  Gate Recording Procedure with `gate_name=build_verified`,
  `status=<build_verdict>` (`pass` | `skip` | `fail`),
  `fields="type=machine verifier=verify_build"`. `skip` is already valid in
  `gate-recording.md`'s status vocabulary — this is design point 3's answer: a
  legacy skip is recorded as a ledger `skip`, exactly like the gate path's.
- **`.claude/skills/aitask-pickrem/SKILL.md.j2`** (≈ 299–306) and
  **`.claude/skills/aitask-pickweb/SKILL.md.j2`** (≈ 221–228): same replacement.
  Neither records `build_verified`, so neither gains a recording step.
- Add the procedure to SKILL.md's **Procedures** list (§ before `## Notes`).
- Update `gate-recording.md`'s "exactly two files with such call sites"
  paragraph only if it becomes untrue — it does not (the recording stays in
  SKILL.md).

**Adjacent and deliberately not fixed here.** Step 9's existing
`gates_out="$(./ait gates run …)"; gates_rc=$?` carries the same errexit hazard.
It is far less harmful there — every nonzero status from that call *is* an
infrastructure failure the branch would abort on anyway — and rewriting it would
churn the Step 9 goldens for a case this task does not own. Note it in the Final
Implementation Notes and let Step 8's follow-up hooks decide, rather than
widening this change.

## 5. `aitask-qa` (design point 4 — same blind spot, fixed)

`.claude/skills/aitask-qa/test-execution.md` §4b runs `test_command` /
`lint_command` directly, so an opted-in command's exit 2 scores as a failed
component. Routing the run through the helper is necessary but **not
sufficient**: §4d line 57 reads *"If no tests found **or run**, score 0"*, §4c's
display format has only `PASS` / `FAIL`, and §4e's evidence table has no skip
disposition — so a correct helper would still produce a false failure or an
inconsistent score. Each of the four surfaces gets an explicit rule:

- **§4b (run).** Route each **configured** key through the helper and keep its
  `VERDICT` / `REASON` per key. Auto-detected commands (no config key) keep
  today's direct-run path — the helper only speaks config keys, and an
  auto-detected runner never opted into the contract. Change "Collect pass/fail
  results" to "Collect pass / fail / **did-not-run** results".
- **§4c (present).** Add a third row form so a skip is visible and not silently
  absent: `tools/run-tests.sh ...... SKIP (did not run — exit 2)`.
- **§4d (score).** Amend the Tests rule so the two cases it currently conflates
  are separated: *no tests found* stays **0** (a real gap in coverage), while a
  command that **declared it did not run** is **N/A** — excluded from the
  denominator and its weight redistributed, exactly like the existing missing-
  `lint_command` case. Scoring a skip 0 is the same category error the gate path
  was fixed for. Extend §4d's closing N/A sentence from "(e.g., no lint command)"
  to also name the did-not-run case.
- **§4e (verification gate, tier `e`).** Step 1 of the gate — *"Re-run all tests
  fresh (not cached) — run the full test command again"* — is a **second
  execution site**, and amending §4b alone leaves it raw. State explicitly that
  the fresh re-run goes through the **same helper**, or an opted-in exit 2 is
  read as a plain failure during verification despite every new SKIP/N/A rule
  upstream. Then define the outcome:
  - Because it is a genuinely fresh run, it may legitimately return a
    *different* verdict from §4b (the lock the runner was waiting on may have
    cleared, or may have been taken). That is **not** a discrepancy under step 5
    and must not be reported as one.
  - A `VERDICT:skip` on the fresh run makes the "All tests pass" row
    **unverified, not false** — `Verified: No`, with the helper's `DETAIL` as
    the evidence cell, routed to step 4's existing "flag unverified claims"
    branch. It is neither a pass nor a failure, and step 5's "report the
    discrepancy and ask the user how to proceed" does not fire for it.

One sentence points at `build-verification.md` for the exit-contract rule
itself; the table is not restated here.

## 6. Documentation — state which behavior applies where

- `aidocs/gates/aitask-gate-framework.md` (verifier exit-code section, ≈ 358):
  add that the same contract now governs the legacy prose path via
  `aitask_run_project_command.sh`, and that a legacy skip is recorded as a
  ledger `skip`.
- `website/content/docs/skills/aitask-pick/build-verification.md`: the "When
  these commands are run as **gates**" scoping is now wrong. Restate it as
  covering both paths and say what a skip means on each (gate: satisfied,
  dependents released; legacy: proceed, recorded as `skip`, agent not sent back
  to fix).
- `seed/project_config.yaml`'s `gate_command_exit_contract` comment block: one
  sentence that the contract also governs the Step-9 build-verification step,
  not only the three gates.

### Post-phase (risk mitigations)

1. `[assert_qa_exit_contract_prose]` After the `aitask-qa` edit lands, add a
   rendered-prose assertion to `tests/test_skill_render_aitask_qa.sh`: render
   `test-execution.md` for each committed profile and assert **one pin per
   amended surface** — §4b names `aitask_run_project_command.sh`, §4c carries the
   `SKIP (did not run` row form, §4d no longer says tests that did not *run*
   score 0, and §4e names the did-not-run claim as unverified. Four surfaces
   changed, so a single "mentions the helper" assertion would pass with three of
   them reverted. `test-execution.md` has no golden, so these are the only things
   that can fail if §5 is dropped or rendered wrong. Pin short, single-line
   phrases — a pin that wraps in the rendered output guards nothing. Verify the
   assertion is reachable by temporarily reverting the §5 edit and observing it
   fail.

---

## Verification

**New `tests/test_run_project_command.sh`** — fixture dirs with a synthetic
`project_config.yaml`, modelled on `tests/test_gate_verifiers.sh`'s
`new_fixture` / `write_config` helpers:

| # | fixture | expected |
|---|---|---|
| A | key absent | `skip` / `none_configured`, rc 2 |
| B | `exit 0`, opted in | `pass` / `all_passed`, rc 0 |
| C | **`exit 1`, opted in** | **`fail` / `command_failed`, rc 1** ← the reachable rejection probe |
| D | `exit 1`, not opted in | `fail`, rc 1 |
| E | `exit 2`, opted in | `skip` / `command_skipped`, rc 2 |
| F | `exit 2`, **not** opted in | `fail`, rc 1 |
| G | `exit 3`, opted in | `fail`, rc 1 |
| H | list `[exit 2, exit 1]`, opted in | `fail` — a skip does not short-circuit |
| I | list `[exit 2, exit 0]`, opted in | `skip` |
| J | opt-in list has a bogus key | `NOTE:` line present, verdict unchanged |
| K | bad `<config_key>` argument | rc 3, **no** `VERDICT:` line |
| L | any run | the log file holds the command's output |

Run C and F **before** writing the fix and confirm they fail against a
deliberately-wrong helper stub, so the probe is observed failing rather than
assumed reachable.

**End-to-end decision flow** — A through L prove the helper's exit table and the
render tests prove the prose *references* the procedure, but neither exercises
the path an agent actually walks. A wiring error could still leave `VERDICT:skip`
read as a failure, an absent command mishandled, or a list stopped after a skip,
with every static test green. So add `test_legacy_build_verification_flow` to the
new file, which drives the **documented invocation verbatim** — the same block
the procedure renders, not a hand-tuned equivalent — **from inside a
`set -euo pipefail` script**, across four fixtures, asserting the values an agent
would branch on. The strict-shell wrapper is not incidental: it is the regression
test for the capture shape, and the rejected `bv_out=…; bv_rc=$?` form fails it
outright.

| fixture | `bv_rc` | `bv_verdict` | `bv_reason` | agent must |
|---|---|---|---|---|
| key absent | 2 | `skip` | `none_configured` | skip the step; record nothing |
| `exit 2`, opted in | 2 | `skip` | `command_skipped` | proceed; **not** go fix a build |
| `exit 1`, opted in | 1 | `fail` | `command_failed` | go fix a build |
| `[exit 2, exit 1]`, opted in | 1 | `fail` | `command_failed` | go fix a build — the skip did not short-circuit |

Every row must be reached: a fixture that aborts the wrapper script at the
capture never reports a verdict at all, so `REACHED END` is asserted too — an
errexit regression must fail loudly rather than silently shrinking the table.

Paired with a **copy-safety pin**: assert the rendered `build-verification.md`
contains the helper invocation line byte-for-byte as the test runs it (one
rendered line, so the pin cannot be defeated by wrapping). That is what makes
this an end-to-end check of the *documented* flow rather than of a private
reimplementation of it — if someone edits the snippet in the procedure, the pin
fails; if the snippet stops producing these verdicts, the table fails.

The remaining half — whether the agent *obeys* the branch — is agent behavior
and not shell-testable. Offer it as a manual-verification follow-up at Step 8c
rather than claiming test coverage for it.

Two more, which are the executable form of the acceptance criteria:

- **Cross-path parity** — for the same fixture, run `aitask_gate_build.sh` and
  `aitask_run_project_command.sh verify_build` and assert both report `skip` for
  the opted-in exit 2 and both report `fail` for exit 1. This asserts the two
  paths agree directly rather than inferring it from shared code.
- **Allowlist coverage** — the helper appears in all 5 policy files (copy
  `test_verification_stale.sh`'s `test_helper_is_in_every_invocation_allowlist`).
- **Single canonical place** — none of `task-workflow/SKILL.md`,
  `aitask-pickrem/SKILL.md.j2`, `aitask-pickweb/SKILL.md.j2` still contains the
  old restatement `stop on first failure`, and each references
  `build-verification.md`.

**`tests/test_skill_render_task_workflow.sh`** — add `build-verification.md` to
`WRAPPED_FILES_INVARIANT` (no Jinja ⇒ one canonical golden + the invariance
assertion). Update Test 6's `gate_name=build_verified` assertion to also pin
`status=<build_verdict>`, so the verdict-driven recording is covered.

**Existing suites that must pass unchanged:**
```bash
bash tests/test_gate_verifiers.sh          # ledger fields byte-identical
bash tests/test_run_project_command.sh     # new
bash tests/test_skill_render_task_workflow.sh
bash tests/test_skill_render_aitask_qa.sh
bash tests/test_skill_verify.sh
./.aitask-scripts/aitask_skill_verify.sh   # prerender freshness
shellcheck .aitask-scripts/aitask_run_project_command.sh .aitask-scripts/lib/gate_verifier_lib.sh
```

**Goldens + committed prerenders, in the same commit as the source edit:**
- `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
- `tests/golden/procs/task-workflow/build-verification-default.md` (new)
- `tests/golden/skills/aitask-{pickrem,pickweb}/SKILL-remote-claude.md`
- `tests/golden/skills/aitask-qa/SKILL-*-claude.md` **only if** qa's `SKILL.md.j2`
  changes — the edit is in `test-execution.md`, which has no golden
- `./.aitask-scripts/aitask_skill_rerender.sh remote` → commit the refreshed
  `.claude/skills/task-workflow-remote-`,
  `.agents/skills/task-workflow-remote-codex-`,
  `.opencode/skills/task-workflow-remote-` and the pickrem/pickweb remote trees.

**Review the golden diff, don't rubber-stamp it** — the intended diff is the
Step-9 block shrinking to a reference plus the verdict-driven recording line;
anything else is a regression.

**End-to-end manual check** — in a scratch fixture with
`verify_build: "exit 2"` and `gate_command_exit_contract: [verify_build]`, run
the helper and confirm `VERDICT:skip` / `REASON:command_skipped`, then flip the
command to `exit 1` and confirm `VERDICT:fail`.

## Working-tree note

The tree carries unrelated uncommitted work from a concurrent session
(monitor / board / `test_scaffold.sh` / `dep_resolution.py`). None of it
overlaps the files above. Commit **path-scoped** (`git commit -o -- <paths>`),
never `git commit -a`.

## Step 9

Post-implementation (cleanup, archival, merge) follows task-workflow Step 9.

## Risk

### Code-health risk: medium
- Extracting the command-list runner out of `run_command_gate` changes a load-bearing gate path; the appended ledger block's `result=` text is **not** currently asserted by `tests/test_gate_verifiers.sh` (it pins `status=` and exit codes only), so a wording drift during extraction would ship silently and the orchestrator's recorded history would change shape. · severity: medium · → mitigation: inline pre-phase pin_gate_ledger_result_strings
- Wide file count for a small semantic change — 1 lib, 3 skill sources, 1 qa procedure, 5 policy files, ~8 goldens, 3 committed remote closures, 3 doc sites. Each edit is mechanically verified by an existing guard (`aitask_skill_verify.sh` prerender freshness, golden diffs, the allowlist test), so the blast radius is broad but not silent. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The `aitask-qa` §5 edit lands in `test-execution.md`, which has **no golden and no rendered-prose assertion** — unlike the three legacy sites, nothing would fail if that edit were dropped, reverted, or rendered wrong. It also spans four surfaces (run / present / score / verification gate), so a partial revert is the likely failure shape, not a total one. · severity: medium · → mitigation: inline post-phase assert_qa_exit_contract_prose
- The prose paths are agent instructions: a correct helper plus a correct reference does not prove the agent branches correctly on `VERDICT:skip`. The end-to-end fixture closes the mechanical half (the documented invocation really yields these verdicts) but not the behavioral half. · severity: low · → mitigation: none needed — offered as a manual-verification follow-up at Step 8c rather than claimed as test coverage
- Approach, requirement coverage and feasibility are all pinned: the helper is what the task's own design point 2 prefers, every acceptance bullet has a named deliverable and a test, and the two load-bearing assumptions (sibling `.md` refs auto-join the render closure; the exit table has exactly one home) were verified against `skill_template.py` and `gate_verifier_lib.sh` during exploration. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: pin_gate_ledger_result_strings | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — extraction could silently reword the appended `result=` text | desc: Pin `run_command_gate`'s ledger `result=` string for all four outcomes in tests/test_gate_verifiers.sh before extracting the runner
- timing: post-phase | name: assert_qa_exit_contract_prose | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the aitask-qa edit has no golden and no render assertion | desc: Assert in tests/test_skill_render_aitask_qa.sh one pin per amended surface of test-execution.md (4b helper call, 4c SKIP row, 4d no did-not-run zero, 4e unverified claim)

---

## Final Implementation Notes

**Landed as planned**, with the pre-phase and post-phase mitigations both executed.

### What changed

| File | Change |
|---|---|
| `.aitask-scripts/lib/gate_verifier_lib.sh` | Extracted `run_project_command_key()` — the canonical exit-contract implementation — out of `run_command_gate()`, which is now a thin ledger-appending wrapper around it. Header docblock names both consumers. |
| `.aitask-scripts/aitask_run_project_command.sh` | **New.** CLI over that function; `KEY:value` stdout, exit `0/1/2/3`, no ledger. |
| `.claude/skills/task-workflow/build-verification.md` | **New.** The one prose statement of the legacy run-and-branch rules, incl. the copy-safe invocation block. |
| `task-workflow/SKILL.md`, `aitask-pickrem/SKILL.md.j2`, `aitask-pickweb/SKILL.md.j2` | Restated rules replaced by a reference; Step 9's `build_verified` recording is now verdict-driven (`status=<build_verdict>`, nothing recorded for `none`). |
| `aitask-qa/test-execution.md` | Four surfaces amended (4b run, 4c present, 4d score, 4e verification gate). |
| `aidocs/gates/aitask-gate-framework.md`, `website/.../build-verification.md`, `seed/project_config.yaml` | State that the contract governs both paths, and what a skip means on each. |
| 5 policy files | Helper whitelisted (one entry each). |

### Deviations from the plan

1. **A fifth `REASON` value, `command_malformed`.** The plan's contract listed
   four. During extraction the suite caught that my rewrite had dropped t1609's
   `bash -n` unparseable-command guard — a hazard landed *between* my first read
   of the lib and my edit, so the whole-file rewrite was built on a stale
   snapshot. Restored from HEAD and given its own reason value (it is a `fail`,
   never a skip: bash exits 2 on a syntax error, which collides with the skip
   code). Pinned by a new row in `tests/test_run_project_command.sh` (G2).
2. **`run_project_command_key` can return 3.** The plan had it always return a
   verdict. It now returns 3 when `yaml_utils.sh` was not sourced — without that,
   a missing reader resolves every key to zero commands and reports a confident,
   wrong `skip`. The check lives inside the function, not at file scope: sourcing
   the lib only to read `GATE_COMMAND_KEYS` is legitimate (`test_gate_verifiers.sh`
   Test 10 does exactly that), and a file-scope `exit` would kill the sourcing
   shell. `run_command_gate` propagates it as verifier `error` and appends nothing.

### Fixed during Step-8 review

Two defects the user caught in review; both reproduced before changing anything.

3. **A log the helper cannot write produced a confident WRONG verdict** (`aitask_run_project_command.sh`).
   The `--log` branch swallowed a failed `mkdir -p` with `|| true` and never
   checked writability, so `--log /proc/nope/out.log` returned a verdict with a
   `LOG:` path holding nothing. Worse than the missing diagnostics: the runner's
   parse check is `bash -n -c "$c" 2>>"$log"`, so an unwritable log makes bash
   fail on the **redirection** before parsing, and a perfectly valid command came
   back as `REASON:command_malformed` — reproduced verbatim. Every log branch now
   funnels through one `: > "$log_path"` writability proof and a log-setup
   failure is an infrastructure error (exit 3, **no** verdict line), never a
   verdict. The script also now uses the repo-standard `set -euo pipefail`,
   matching the gate wrappers that source the same lib. Pinned by rows M
   (uncreatable parent), M2 (unwritable file) and M3 — a positive control proving
   the same command grades `command_failed` against a writable log, so M/M2
   cannot pass merely because the helper stopped working.

4. **The qa `N/A` rule could redistribute a real failure out of the score**
   (`test-execution.md`). Marking the whole Tests component N/A whenever the
   configured `test_command` reported `skip` ignored that 4b *also* runs
   individual changed-source tests directly: a skipped runner beside a failing
   direct test displayed the failure in 4c and then dropped it from the score.
   N/A is now conditional on there being **no other executed evidence** — the
   score is computed over every test that actually ran, a direct failure always
   counts, and 4e's fresh re-run no longer scopes its "unverified" row wider than
   the claim the skipped runner actually backed. Pinned by four new render
   assertions (one per corrected surface).

### Upstream defects identified

- `.claude/skills/task-workflow/SKILL.md:806` — the Step-9 gate dispatch uses
  `gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?`, which under
  `set -e` terminates the shell at the assignment before `gates_rc` is captured.
  Same class as the helper defect fixed in this task (and verified there by a
  live probe), pre-existing and in a different block.
- `.claude/skills/aitask-pickrem/SKILL.md.j2:368` — the same capture shape, same
  defect, in pickrem's gate dispatch.

### Adjacent issue found, deliberately not fixed

Step 9's pre-existing `gates_out="$(./ait gates run …)"; gates_rc=$?` carries the
same errexit hazard this task documents for the new helper: under `set -e` the
shell dies at the assignment before `gates_rc` is captured. It is far less
harmful there (every nonzero status from that call *is* an abort-worthy
infrastructure failure the branch would stop on anyway), and rewriting it would
churn the Step 9 goldens for a case this task does not own. Left as-is.

### Verification performed

- `tests/test_gate_verifiers.sh` — **149/149**. The four new `Result:` pins were
  confirmed passing against the *un-refactored* code first (the pre-phase
  mitigation's baseline requirement), then again after the extraction.
- `tests/test_run_project_command.sh` — **84/84** (new). Exit table incl. the
  exit-1-under-opt-in rejection probe, list aggregation, NOTE/usage/log,
  cross-path parity against `aitask_gate_build.sh`, and the end-to-end flow
  driven through the documented invocation inside `set -euo pipefail`.
- **Reachability probed, not assumed:** breaking the documented-invocation pin
  produced 5 failures; rewriting the negative-control driver to use the safe
  capture form made the "rejected shape dies" assertion fail. Both assertions
  discriminate.
- `test_skill_render_task_workflow.sh` 200/200 · `test_skill_render_aitask_qa.sh`
  219/219 · `test_skill_verify.sh` 29/29 · `test_skill_render.sh` 28/28 ·
  `test_seed_manifest_drift.sh` 44/44 · `test_setup_agent_config_seeds.sh` 22/22 ·
  `test_agent_instructions.sh` 122/122.
- `./.aitask-scripts/aitask_skill_verify.sh` — OK (13 templates × 3 agents,
  wrapper parity clean). `shellcheck` clean on both shell files (only the
  codebase-wide SC1091 baseline the existing gate wrappers also emit).
- Goldens regenerated and the diff reviewed: the Step-9 block shrinking to a
  reference, the verdict-driven recording line, one new Procedures entry, and the
  four qa surfaces. No unrelated churn.
- `aitask_skill_rerender.sh remote` refreshed all three tracked remote closures;
  per-agent reference rewrites verified (codex →
  `.agents/skills/task-workflow-remote-codex-/build-verification.md`, opencode →
  `.opencode/skills/task-workflow-remote-/build-verification.md`).
- End-to-end manual check: opted-in `exit 2` → `VERDICT:skip` /
  `REASON:command_skipped` (rc 2); flipped to `exit 1` → `VERDICT:fail` /
  `REASON:command_failed` (rc 1).

### Not covered by tests

Whether the agent *obeys* the branch it reads — i.e. actually declines to "fix
the build" on `VERDICT:skip` — is agent behavior and not shell-testable. The
mechanical half (the documented invocation really yields these verdicts) is
pinned; the behavioral half is offered as a manual-verification follow-up.
