---
Task: t1597_pre_implementation_resource_admission_hook.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1597 — Pluggable pre-implementation resource admission hook

## Context

Planning is cheap; implementation and verification are memory-bound (the
downstream repo records a 2026-08-18 OOM that killed a Gradle test worker *and*
its agent). The framework performs **no resource/capacity check anywhere in the
task path** — Step 7's pre-implementation guards are ownership/lock, the deferred
worktree fork, and the risk-mitigation "before" stop. So an operator planning
several tasks in parallel cannot let the workflow itself decide "can this host
afford to start implementing now?"; the decision is manual and a wrong call OOMs
the box mid-verification.

This ships the **seam only**: a project-pluggable command consulted once, at the
Step-7 boundary, whose refusal parks the task on its approved plan. The probe
itself (thresholds, `/proc/meminfo`, PSI) stays in the downstream project.

**Naming (user-confirmed).** The key is `resource_admission_command`, not
`admission_command`: t1569_4 (Ready) wires a *different* admission check — the
parallel-admission preflight, profile knob `parallel_admission: block|warn|off`,
helper `aitask_parallel_admission.sh` — into the same seam. Every surface this
task adds is qualified with `resource_` so neither reader has to guess.

**Disposition (user-confirmed).** Fail closed: a hook that cannot render a
decision parks the task exactly like a refusal, with a message that says so.

**Scope (user-confirmed).** `task-workflow` only. `aitask-pickrem` /
`aitask-pickweb` are self-contained workflows with no drift check and no
interactive stop; the confirmed `after` mitigation
`port_resource_admission_to_remote_picks` (§9) carries the contract to them.

---

### Pre-phase (risk mitigations)

- **`baseline_shared_lib_tests`** — before editing anything, run and record the
  green baseline of the three tests this change moves through shared surfaces:

  ```bash
  bash tests/test_gate_verifiers.sh
  bash tests/test_plan_approved_marker_contract.sh
  bash tests/test_skill_render_task_workflow.sh
  ```

  A failure after the `project_config_values` rename or the `stop_reason` edit is
  only attributable to this task if these were green beforehand. Record the
  result in the plan as you go.

## 1. The helper — `.aitask-scripts/aitask_resource_admission.sh` (new)

Modelled on `aitask_run_project_command.sh` (same house style: pure `KEY:value`
stdout, warnings to stderr, log path is part of the contract).

```
usage: aitask_resource_admission.sh [--task-id <id>] [--plan <path>] [--log <path>]
```

**stdout** (data channel; the hook's own output goes to the LOG, never here):

```
VERDICT:admit|refuse|error                     # absent on exit 3
REASON:none_configured|admitted|refused|command_malformed|command_error|not_scalar
DETAIL:<one-line human text>                   # sanitized (see below)
LOG:<path>|(none)                              # (none) = no command ran, nothing written
DIAG:<one-line sanitized diagnostic>           # exit 3 ONLY, and always on exit 3
```

`DIAG:` exists so the **procedure never has to read stderr**. The prescribed
capture form takes stdout only, and merging stderr in (`2>&1`) would corrupt the
`KEY:value` parse — so an infrastructure outcome that spoke only on stderr would
leave the agent with nothing deterministic to show. It is bounded and sanitized
by the same writer as `DETAIL:` (single line, control characters stripped,
truncated). Human-readable stderr is kept as-is for a terminal user; it is never
part of the contract.

**Helper exit status** — 0 admit · 1 refuse · 2 error (a verdict: the hook ran
but could not decide) · 3 usage/infrastructure (**no `VERDICT:` line**, which is
how a caller tells "could not evaluate" from any verdict). Keeping 2 and 3
distinct is the point: a broken hook and a broken invocation must not be
indistinguishable from each other, even though the prose routes both to the same
park.

**The hook's own exit vocabulary** (a separate namespace from the helper's, as
in `run_project_command_key`'s docblock):

| hook exit | meaning |
|---|---|
| `0` | admit — proceed to implementation |
| `2` (`RESOURCE_ADMISSION_REFUSE_EXIT`, a named constant) | refuse — defer this task |
| anything else | error — the hook could not decide |

`bash -n -c "$cmd"` first: a command that will not parse never ran, so it is
`command_malformed` (error), never a refusal. This is the same reasoning
`gate_verifier_lib.sh` records for `command_malformed` being a fail.

**Reason extraction and sanitizing.** `DETAIL:` prefers the last
`ADMISSION_REASON: <text>` line in the hook's output (namespaced so it cannot
collide with our own `REASON:` key), falls back to the last non-empty output
line, and otherwise reads `no reason given`. It is sanitized **at the write
site**: CR/LF and control characters stripped, whitespace collapsed, truncated
to 200 chars — the text is author-controlled and lands in a line the agent
parses.

**Config read — reuse, do not re-parse.** Rename the private
`_gate_config_values()` in `.aitask-scripts/lib/gate_verifier_lib.sh` to a public
`project_config_values()` (3 call sites, all in that file; two comment
references in `tests/test_gate_verifiers.sh`) and call it from the new helper.
Verified behaviour on a scalar key: `read_yaml_list` yields nothing, the scalar
fallback returns the value with one layer of quotes stripped.

`resource_admission_command` is **scalar-only**, enforced on the YAML **shape**
rather than on a value count: `read_yaml_list` is the shape witness (empty for
every scalar form, non-empty for every list form whatever its length), so ANY
list exits 3 with `not_scalar`. A count-based check would admit a one-element
list while rejecting a two-element one. Scalar-only keeps the Settings TUI's
plain string editor lossless; a project needing several probes writes one
wrapper script.

**Do NOT add the key to `GATE_COMMAND_KEYS`.** `tests/test_gate_verifiers.sh`
Test 10 derives that constant from the `aitask_gate_*.sh` wrappers and fails on
drift, and the semantics differ (refuse ≠ fail).

**Environment handed to the hook** — the whole contract, nothing else:
`AIT_RESOURCE_ADMISSION_TASK_ID`, `AIT_RESOURCE_ADMISSION_PLAN_FILE` (may be
empty).

**Log — resolve the config FIRST, allocate a log only if something will run.**
This deliberately **inverts** `aitask_run_project_command.sh`'s ordering, which
allocates the log before reading the key and then writes "(no X configured)"
into it. That is wrong for a hook on the ordinary path: an unconfigured project
would get a fresh `.aitask-gates/<task-id>/` directory and a timestamped,
audit-looking artifact at **every** Step 7, for a feature it never opted into.

So: read `resource_admission_command`; if it resolves to nothing (key absent,
`null`, empty, or no `project_config.yaml` at all) emit
`VERDICT:admit` / `REASON:none_configured` / `DETAIL:no resource_admission_command configured`
/ `LOG:(none)` and exit 0 having **created nothing** — no directory, no file, not
even with an explicit `--log` (which names where a log *would* go, not a file to
create). `LOG:(none)` is the sentinel for "no command ran", in the house style of
`MATERIALIZED:(empty)`.

Only once a command exists: allocate
`.aitask-gates/<id>/resource_admission_<UTCts>_<pid>.log` with `--task-id`, else
`mktemp`, and prove it writable **before** anything runs — an unwritable log
makes `bash -n` fail on the redirection and reports a valid command as malformed
(the sibling helper documents exactly this).

**"No-op when unset" is therefore literal**: no prompt, no stop, no state
change, no fork difference, no display, and **no filesystem artifact**. Pinned
by its own test (§7.1), which asserts `.aitask-gates/` is not created.

## 2. The procedure — `.claude/skills/task-workflow/resource-admission.md` (new)

Modelled on `remote-drift-check.md`. Profile-invariant: **no Jinja**, so it gets
one canonical golden plus the byte-equality invariance assertion.

- Input context: `task_id`, `task_num`, `plan_file`.
- Run the helper with `--task-id <task_id> --plan <plan_file>`, capturing stdout
  under the `if out="$(…)"; then rc=0; else rc=$?; fi` form the sibling helper's
  docblock prescribes (a bare `out=$(…); rc=$?` dies under `set -e`). **Never
  merge stderr into stdout** — every line the procedure acts on is a `KEY:value`
  line, `DIAG:` included.
- **Exit 0 with `REASON:none_configured`** → **display nothing at all** and
  return to Step 7. An unconfigured project must not learn about this feature
  from a line in every pick.
- **Exit 0 otherwise** → display "Resource admission: admitted (`<DETAIL>`)" and
  return to Step 7.
- **Any non-zero** → park. Never treat a non-zero as admit. Execute the
  **Approved-Plan Stop Sequence** (`plan-approved-stop.md`) with
  `stop_reason=resource_admission`,
  `revert_commit_message="ait: Revert t<task_num> to Ready (resource admission)"`,
  and a `closing_message` selected by the verdict:
  - `refuse` — names the hook's reason, the log path, and the remedy: free the
    resource and re-pick `/aitask-pick <task_id>`; the approved plan is kept, so
    planning is skipped.
  - `error` (helper exit 2) — says the hook **could not be evaluated**, quotes
    the exit status and `DETAIL`, names the log, and adds the second remedy:
    fix or unset `resource_admission_command` in `project_config.yaml`.
  - no `VERDICT:` line (helper exit 3) — reads `DIAG:`, the bounded sanitized
    diagnostic the helper guarantees on this exit, and reports it as a wiring
    error (naming `LOG:` when it is not `(none)`), then routes through the **same
    Approved-Plan Stop Sequence with `stop_reason=resource_admission`** — a
    missing verdict is not an escape from the park. Never quote raw stderr: it is
    not captured, and would be unbounded, unsanitized text.

  A refusal and a broken hook must not look identical — same routing, different
  sentence.
- **Notes.** (a) This is an admission decision at a workflow seam, **not a gate**:
  nothing is appended to the gate ledger (the `plan_approved` recording inside
  the stop sequence is pre-existing and unchanged), so `archive-ready`,
  `resume-point` and `workflow-phase` see no new state. Being a gate would also
  put it at the mercy of `filter_gates_for_issue_type()`, which strips names
  outside its allowlist. (b) **It observes, it does not reserve** — an admit
  means "no known shortage at check time"; another agent can claim the memory
  the instant after. (c) No profile knob: an unset key is already the opt-out,
  and the parked-vs-implement decision must not vary with prompting style.
- **Availability is structural, not statistical** (contrast t1569_4, which ships
  at `warn` because 96 % of picks are UNCHECKABLE): this hook is opt-in and runs
  one local command, so a project that configures it gets a decision every time
  or a named error — there is no evidence-availability question to measure.

## 3. `.claude/skills/task-workflow/SKILL.md` (4 edits)

1. **Step 7 — new block** between `**Pre-implementation ownership guard:**` and
   `**Deferred worktree fork (Step-5 intent, cut now):**`. After ownership (the
   park releases the lock, so ownership must be held) and before the fork (so a
   refusal strands no worktree — the same rationale the deferred fork already
   states). Reaching Step 7 means the plan was approved *and* the drift check
   returned "Continue anyway", so the ordering the task asks for holds on both
   routes by construction.
2. **Re-entry Routing, `IMPLEMENT` route** — extend the re-run list to
   "the **Pre-implementation ownership guard**, the **Resource Admission
   Procedure**, the **Deferred worktree fork** block, and the **Agent
   Attribution Procedure** … in that order". A resumed session is admitted
   again on purpose: the world moved while the task was parked, and the hook is
   idempotent (a pure probe), which is that list's stated criterion.
3. **Procedures index** — one bullet, in the style of its neighbours.
4. **Project Configuration table** — a `resource_admission_command` row
   (`string`, `(none — skip)`, "Command consulted before implementation starts;
   exit 0 admits, exit 2 defers the task with its approved plan", "Step 7").

## 4. `.claude/skills/task-workflow/plan-approved-stop.md` — a third `stop_reason`

The file today says "There is no third case". Extend the closed vocabulary
rather than smuggling the new stop in as `deferred` (which would put a false
`note=deferred` on the ledger entry):

- Call-site list at the top gains `resource-admission.md → resource_admission`.
- Input table: `deferred` | `drift` | `resource_admission`.
- Marker disposition is grouped by **meaning**, not enumerated per site: stops
  that leave an approved plan intact and awaiting implementation (`deferred`,
  `resource_admission`) run `--plan-approved-at now`; the stop that invalidates
  it (`drift`) runs `--plan-approved-at ""`. Still exactly two commands, so
  `tests/test_plan_approved_marker_contract.sh`'s hit counts and its
  `deferred → now → drift → clear` positional interleave survive; the
  `deferred` conditional header grows an `or resource_admission` clause.
- The exhaustiveness guard is rewritten to name all three and keep its
  "anything else: stop and report" fallback.
- Notes: this call site, like the other two, runs **before** the deferred fork,
  so it strands no worktree.

## 5. Configuration and discoverability surfaces

- `seed/project_config.yaml` — commented example beside `lint_command`
  (`# resource_admission_command: "./tools/check_memory.sh"`), with the exit
  contract in one line. This repo's own `project_config.yaml` stays unset:
  unset ⇒ byte-identical behaviour is acceptance criterion #1.
- `.aitask-scripts/settings/settings_app.py` — a `PROJECT_CONFIG_SCHEMA` entry
  (summary + detail). It is deliberately **not** added to the three
  `("verify_build", "test_command", "lint_command")` tuples: those drive the
  multi-line/preset command modal and list handling, and the key is scalar-only,
  so the plain string editor is both sufficient and lossless.
- Helper whitelist, 5 touchpoints, via the framework's own verb:
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_resource_admission`
  then verify against `aidocs/framework/aitasks_extension_points.md`
  ("Adding a new helper script").

## 6. Documentation

- **New** `website/content/docs/skills/aitask-pick/resource-admission.md` —
  sibling of `build-verification.md`: what the hook is, when it runs, the exit
  contract, what a refusal does (parked, plan kept, `ait ls --plan-approved`
  finds it), and a **copy-safe** reference probe:

  ```bash
  #!/usr/bin/env bash
  # exit 0 = admit, exit 2 = defer this task
  avail_gib=$(awk '/^MemAvailable:/ {printf "%d", $2/1048576}' /proc/meminfo)
  if [ "$avail_gib" -lt 8 ]; then
      echo "ADMISSION_REASON: only ${avail_gib} GiB available, need 8"
      exit 2
  fi
  ```

- `website/content/docs/skills/aitask-pick/_index.md` — step 8 gains one clause
  naming the check before the fork, linking the new page.
- `website/content/docs/skills/aitask-pick/build-verification.md` — one
  cross-reference line, so the "project_config.yaml command keys" page does not
  silently claim to list them all.
- `aidocs/gates/ledger-driven-reentry.md` — the marker section currently says
  the marker is "written **only** by the `deferred` stop" and that "Both
  branches share one implementation". Both statements become untrue: add the
  `resource_admission` row to the lifecycle table and correct the two claims.

## 7. Tests

- **New `tests/test_resource_admission.sh`**, two labelled sections:
  1. *Helper, driven for real* in a synthetic project dir (real subprocesses,
     no mocks): key unset **and no `project_config.yaml` at all** →
     `admit`/`none_configured`, `LOG:(none)`, exit 0, **and `.aitask-gates/` is
     not created** — asserted for the bare call and for one with an explicit
     `--log` (the one path allowed to proceed without a decision, and it must
     leave nothing behind) · hook `exit 0` →
     admit · hook `exit 2` → refuse, with the `ADMISSION_REASON:` line surfaced
     in `DETAIL:` · reason fallback to the last non-empty line · a reason
     carrying newlines/ANSI/1 KiB of text → single sanitized truncated line
     (`DETAIL:` still exactly one line) · `exit 127` and `exit 1` → `error`,
     exit 2 · unparseable command → `command_malformed`, **not** a refusal ·
     list-valued key → exit 3 · unwritable log → exit 3 · a bad `--task-id` →
     exit 3. **Every exit-3 case asserts the same two properties**: no `VERDICT:`
     line, and exactly one `DIAG:` line that is single-line and control-character
     free (drive one of them with a hook path containing newlines and ANSI so the
     sanitizer is exercised on the diagnostic, not only on `DETAIL`) · env vars
     visible to the hook · the hook's chatter lands in the LOG and never on
     stdout. **Negative control:** a hook that exits 0 must produce no refusal,
     so the refusal assertions can fail.
  2. *Rendered-prose seam contract* (the pattern
     `test_plan_approved_marker_contract.sh` uses — line numbers via
     `grep -n`), over `task-workflow-{default,fast,remote}-/`:
     - **Placement** in `SKILL.md`: the admission block sits **after** the
       ownership guard and **before** the deferred fork; Re-entry Routing's
       `IMPLEMENT` list names it between the same two; the procedure is
       referenced exactly once.
     - **The exit-3 branch of `resource-admission.md` is pinned by content, not
       just by existence** — placement and reference counts stay green while a
       later prose edit merges stderr, drops `DIAG:`, or lets a missing verdict
       fall out of the park. **Assert against the extracted branch, never the
       whole file**: the file legitimately names `DIAG:` in the contract recap
       above the branch, so a file-scoped "appears exactly once / nowhere else"
       count would fail on the correct implementation, and relaxing it to a
       file-scoped "appears somewhere" would pass on a build that dropped it
       from the branch. Slice first, then assert inside the slice:
       - **Slice**: from the line matching `helper exit 3` to the line before the
         next sibling bullet (`^- \*\*`) or the next `^#` heading, whichever
         comes first. A slice that comes back empty (the marker was reworded) is
         a **failure**, not a skip — an empty extraction must never look like a
         satisfied assertion.
       - Inside the slice: `DIAG:` appears at least once, and
         `stop_reason=resource_admission` appears at least once — the routing has
         to be spelled *in the branch*, so a missing verdict provably parks
         rather than returning to Step 7.
       - File-scoped, and deliberately so: **no fenced command block contains
         `2>&1`** — an absence check over the ``` fences, not over the prose, so
         the "never merge stderr" sentence that must quote the token does not
         satisfy its own rule.
- **New `tests/test_resource_admission_stop.sh`** — the refusal **lifecycle**,
  driven end to end on the fixture shape of `tests/test_plan_approved_marker_drift.sh`
  (a real origin/clone pair, a marked task and its externalized plan). The helper
  test and the prose test can both be green while the park itself is broken by a
  typo in the stop-sequence arguments, so this is the third link that closes the
  chain: the contract test pins *prose ⇄ command*, this pins *command ⇄ state*.
  1. Apply the documented `stop_reason=resource_admission` revert
     (`--status Ready --assigned-to "" --plan-approved-at now`) and assert the
     parked contract: `status: Ready`, `assigned_to` cleared, `plan_approved_at`
     stamped, `Plan: approved` in `ait ls -v`, one hit from
     `ait ls --plan-approved`, the plan file still present and committed, and
     **no** `aitask/<task_name>` branch and **no** `aiwork/` worktree.
  2. The admitted re-entry prerequisite: on the same fixture, the helper with an
     admitting hook returns exit 0 — the state the workflow then resumes from.
  3. **Negative control:** the `stop_reason=drift` revert on the same fixture
     clears the marker, so step 1's assertions can fail.
- **Extend `tests/test_plan_approved_marker_contract.sh`**: the
  `resource_admission` reason exists, selects the stamping command, and the
  three-way interleave still holds (a `resource_admission` stop must not be able
  to reach the clearing command).
- **Extend `tests/test_skill_render_task_workflow.sh`**: add
  `resource-admission.md` to `WRAPPED_FILES_INVARIANT` and fix the stale
  file/golden counts in the header comment.
- Uses `assert_counters_init` / `assert_counters_load` if any body runs in a
  `( … )` subshell (CLAUDE.md).

## 8. Coordination with t1569_4 (same seam, different check)

t1569_4 (`aitasks/t1569/t1569_4_task_workflow_parallel_admission_preflight.md`,
Ready) will wire the **parallel**-admission preflight into the same boundary,
from `planning.md`'s Checkpoint and Re-entry Routing. Append a
`## Coordination — resource admission (t1597)` section to that task file — the
same way t1643 appended its own coordination section there — recording:

- the two checks are distinct and separately named (`parallel_admission` profile
  knob vs `resource_admission_command` project key; `parallel-admission.md` vs
  `resource-admission.md`); neither may be folded into the other;
- **ordering, if both are wired: correctness before capacity.** The parallel
  preflight (which can stop-and-replan) runs first; the resource hook runs last,
  immediately before the fork. t1569_4's own call sites already satisfy this —
  the Checkpoint precedes Step 7 — so nothing in its plan has to change;
- their dispositions differ on purpose: a CONFLICT stops and replans, a resource
  refusal **parks with the plan intact** (`stop_reason=resource_admission`).

The reverse link lives in `resource-admission.md`'s notes, so the two procedures
point at each other rather than one silently owning the seam.

## 9. Follow-up — the confirmed `after` mitigation

`port_resource_admission_to_remote_picks` is created at **Step 8d** by the
Risk-Mitigation Follow-up Procedure (Part 3) from the `### Planned mitigations`
line below — not hand-rolled here. It carries the same helper and the same exit
contract to `aitask-pickrem` and `aitask-pickweb`, whose park semantics differ
(no drift check, no prompts, and `aitask-pickweb` cannot touch other branches).

## Verification

```bash
# 1. helper + seam contract
bash tests/test_resource_admission.sh
bash tests/test_resource_admission_stop.sh
bash tests/test_plan_approved_marker_contract.sh
bash tests/test_plan_approved_marker_drift.sh
bash tests/test_gate_verifiers.sh            # the project_config_values rename
shellcheck .aitask-scripts/aitask_resource_admission.sh .aitask-scripts/lib/gate_verifier_lib.sh

# 2. re-render every profile closure, then goldens (same commit)
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for f in SKILL plan-approved-stop; do for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py ".claude/skills/task-workflow/$f.md" \
    "aitasks/metadata/profiles/$p.yaml" claude > "tests/golden/procs/task-workflow/$f-$p.md"
done; done
"$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/task-workflow/resource-admission.md \
  aitasks/metadata/profiles/default.yaml claude \
  > tests/golden/procs/task-workflow/resource-admission-default.md
bash tests/test_skill_render_task_workflow.sh
./.aitask-scripts/aitask_skill_verify.sh

# 3. whole suite (read the LAST line only)
bash tests/run_all_python_tests.sh
```

**End-to-end, by hand** (the acceptance sketch through the *real* workflow;
steps 2-3's state assertions are already automated in
`tests/test_resource_admission_stop.sh` — this run proves the agent reaches them
through the prose, which no test can):

1. `resource_admission_command` unset → pick a task, reach Step 7: nothing is
   displayed, nothing changes, and `.aitask-gates/<id>/` does not appear.
2. Point it at `sh -c 'echo "ADMISSION_REASON: no memory"; exit 2'` → the picked
   task plans to approval, parks with the reason shown, `status: Ready`,
   `plan_approved_at` stamped, `ait ls --plan-approved` lists it, and **no**
   `aitask/<task_name>` branch or `aiwork/` worktree exists.
3. Re-pick it under `fast` (`plan_preference: use_current`) with the hook now
   exiting 0 → drift check → worktree fork → implementation, no re-planning.
4. Point it at a missing binary → helper **exit 2** (`command_error`): parks
   with the "could not be evaluated" wording, quoting exit 127 and the log path.
5. Give the key a **list** value → helper **exit 3**, the only path with no
   `VERDICT:` line: the same park, with the message built from `DIAG:`. Exit 3
   is otherwise unreachable from a plausible hook, so it needs its own scenario
   here — step 4 does not reach it.

## Risk

### Code-health risk: medium
- The `plan-approved-stop.md` `stop_reason` edit lands on the framework's most safety-critical stop path: getting the grouping wrong lets a `drift` stop stamp the marker (advertising a plan as implementation-ready on the very path that established it needs re-verification) or lets a `resource_admission` stop clear it · severity: medium · → mitigation: inline pre-phase baseline_shared_lib_tests
- Renaming `_gate_config_values` → `project_config_values` sits on the code path of all three machine gates (`build_verified` / `tests_pass` / `lint`); a missed call site breaks every command gate at once · severity: medium · → mitigation: inline pre-phase baseline_shared_lib_tests
- The Step-7 insertion is prose inside a 1000-line rendered file: a placement after the deferred fork, or a forgotten Re-entry-Routing list edit, is invisible without a positional assertion and would strand a worktree on every refusal · severity: medium · → mitigation: none needed (§7.2's positional seam test is a plan deliverable)
- Six rendered closures (3 profiles × the shared procedures) plus 4 goldens must move together; a stale render ships a workflow whose prose and goldens disagree · severity: low · → mitigation: inline pre-phase baseline_shared_lib_tests

### Goal-achievement risk: low
- The seam covers `task-workflow` only, so `aitask-pickrem` / `aitask-pickweb` keep starting memory-bound phases unadmitted — the stated goal is met for attended picks and deferred for autonomous ones (user-confirmed scope) · severity: low · → mitigation: port_resource_admission_to_remote_picks
- A refusal parks on the approved plan and relies on §6.0's existing-plan preference to skip re-planning; under `default` (no `plan_preference`) the user still sees the 3-way prompt, now with the marker's "Use current plan (Recommended)" — the acceptance sketch's no-replan claim holds under `use_current`, which is what it says · severity: low · → mitigation: none needed (documented behaviour)

### Planned mitigations
- timing: pre-phase | name: baseline_shared_lib_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (shared-lib rename, stop_reason edit, closure/golden freshness) | desc: Record a green baseline of test_gate_verifiers, test_plan_approved_marker_contract and test_skill_render_task_workflow before any edit
- timing: after | name: port_resource_admission_to_remote_picks | type: feature | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement (autonomous picks start memory-bound phases unadmitted) | desc: Carry the resource-admission hook to aitask-pickrem and aitask-pickweb with their own park semantics


## Post-Review Changes

### Change Request 1 (2026-09-01 12:57)
- **Requested by user:** The scalar-only contract was documented but not
  enforced. `aitask_resource_admission.sh` rejected only *more than one*
  resolved value, so `resource_admission_command: ["exit 0"]` was admitted and
  ran — `project_config_values()` is shape-agnostic and had already flattened
  the list, so the implementation could not enforce the contract it described.
  Preserve the scalar-vs-list shape during resolution and add a single-item-list
  negative test.
- **Verified before changing anything:** a probe over seven YAML shapes confirmed
  both halves — the one-element list really was admitted, and `read_yaml_list`
  really is a sound shape witness: 0 values for every scalar form (including
  `"pytest -k 'a,b'"`, whose comma must not read as a list) and ≥1 for every
  list form regardless of length.
- **Changes made:** the helper now asks `read_yaml_list` first and refuses the
  list **form** outright, before any count; `project_config_values()` is used
  only for the scalar path, so no third parser is introduced. The old
  count-based check is kept as a defensive backstop with a comment saying it can
  no longer be the enforcement point. Four list cases (inline/block × 1/2 items)
  and a comma-containing-scalar negative control were added. Mutation-checked:
  disabling the shape check reproduces the reported defect and fails 14
  assertions.
- **Files affected:** `.aitask-scripts/aitask_resource_admission.sh`,
  `tests/test_resource_admission.sh`,
  `website/content/docs/skills/aitask-pick/resource-admission.md`,
  `seed/project_config.yaml`.
