# Build Verification Procedure

Runs a `project_config.yaml` command key — `verify_build` by default — and turns
its result into a workflow decision. This is the **legacy** (non-gate) build
verification path: it fires when a task has not opted into the gate system, and
it is the only place that path's run-and-branch rules are written down.

It exists so the three skills that perform legacy build verification —
`task-workflow` Step 9, `aitask-pickrem` and `aitask-pickweb` — stop restating
the rules independently and stop disagreeing with the gate verifiers about what
a command's exit code means (t1610).

**The exit contract itself is not documented here.** It lives in exactly one
place: `run_project_command_key()`'s docblock in
`.aitask-scripts/lib/gate_verifier_lib.sh`, which the `build_verified` /
`tests_pass` / `lint` gate verifiers and the helper below both execute. That is
what makes the two paths agree by construction rather than by proofreading.

## Input context

| Variable | Description |
|----------|-------------|
| `config_key` | The `project_config.yaml` key to run. Defaults to `verify_build`. |
| `task_id` | Optional. When set, the run's log is written under `.aitask-gates/<task_id>/` beside that task's gate logs. |

## Return contract

Threads two values back into the calling workflow:

- `build_verdict` — `pass` \| `fail` \| `skip` \| `none`.
- `build_log` — path to the log holding the command's own output.

`none` means *nothing was configured*, so there is nothing to report and nothing
to record. `skip` means a configured command **ran and declared it did not do
the work** — a real, recordable outcome. Do not collapse the two.

## Procedure

### 1. Run the helper

Exit `1` and exit `2` are both **normal outcomes** of this call, so the status
must be captured in a form that survives `set -e`. Use exactly this block:

```bash
if bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id <task_id>)"; then
  bv_rc=0
else
  bv_rc=$?
fi
bv_verdict="$(printf '%s\n' "$bv_out" | sed -n 's/^VERDICT://p')"
bv_reason="$(printf '%s\n' "$bv_out" | sed -n 's/^REASON://p')"
bv_detail="$(printf '%s\n' "$bv_out" | sed -n 's/^DETAIL://p')"
bv_log="$(printf '%s\n' "$bv_out" | sed -n 's/^LOG://p')"
bv_note="$(printf '%s\n' "$bv_out" | sed -n 's/^NOTE://p')"
```

Drop `--task-id <task_id>` when no task id is in scope; the helper then logs to a
temporary file and reports its path on the `LOG:` line either way.

**Do not write `bv_out="$(…)"; bv_rc=$?`.** Under `set -e` those are two separate
simple commands: the assignment inherits the command substitution's non-zero
status, errexit fires, and the shell exits before `bv_rc=$?` runs — so the skip
this whole procedure exists to handle would kill the caller instead. The `if`
form works because errexit is suspended inside an `if` condition.

**Do not add `2>&1`.** The helper's stderr is a human-facing warning channel;
merging it into stdout corrupts the `KEY:value` parse. Every machine-readable
value, warnings included, is already on stdout.

Then branch on `bv_verdict`. `bv_rc` is a cross-check, never the primary signal.

### 2. `bv_rc` is 3, or `bv_verdict` is empty — infrastructure failure

The helper could not evaluate the key at all (bad argument, unreadable
environment). This is **not** a build failure: do not "fix the code", do not
record a gate, and do not treat it as a pass. Report the helper's stderr and
diagnose the configuration. An empty verdict is not a verdict.

### 3. `pass` — proceed

Display that build verification passed. Set `build_verdict = pass`.

### 4. `skip` + reason `none_configured` — nothing to do

Display: "No `<config_key>` configured — skipping build verification."
Set `build_verdict = none`.

### 5. `skip` + reason `command_skipped` — the command declared it did not run

The command exited with the documented did-not-run code and its key is listed in
`project_config.yaml`'s `gate_command_exit_contract`, so the project has
explicitly declared that this means *"I did not run"* — a test runner serialized
behind a host-global lock another agent holds, for example.

**Do NOT go back and fix a build.** Nothing failed. Print `bv_detail` so the skip
is visible in the transcript rather than looking like a silent pass, then
proceed. Set `build_verdict = skip`.

This is the outcome the gate path records as a ledger `skip`, and the caller
records it the same way — that agreement is the point.

### 6. `fail` — the ordinary build-failure loop

Read `bv_log` and compare the error output against the changes this task
introduced (`git diff` against the base):

1. **Caused by this task's changes** — go back to the implementation, fix the
   errors, then re-run the block in step 1. Repeat until it no longer fails.
2. **Not related to this task's changes** (pre-existing issue, environment
   problem) — log the failure details in the plan file's "Final Implementation
   Notes" section under a "Build verification" entry and proceed. Do not attempt
   to fix pre-existing issues.

Set `build_verdict = fail`.

### 7. A `NOTE:` line is present — surface it

`bv_note` is non-empty only when `gate_command_exit_contract` lists a key that is
not one of `verify_build` / `test_command` / `lint_command`. The entry is ignored
and never changes a verdict, but show it to the user: a misspelled key produces
exactly the behavior of "not opted in", which is the hardest state to diagnose
from the outcome alone. This is independent of the verdict — check it on every
branch above.
