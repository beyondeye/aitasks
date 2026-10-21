---
Task: t2085_fix_remote_drift_check_errexit_guard_failure.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t2085 — make the remote drift check's `DRIFT_RC` capture errexit-safe

## Context

`tests/test_skill_errexit_capture.sh` Test 4 (the surface-wide errexit guard)
fails at HEAD: 65/66. Its scanner flags two fenced-bash lines in
`.claude/skills/task-workflow/remote-drift-check.md` that t2061 (`c643a8390`)
added:

```
:27  ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; echo "DRIFT_RC:$?"
:42  ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "$output_branch" "<plan_file>"; echo "DRIFT_RC:$?"
```

(The task body names only :27; the guard reports both.) Under `set -e`, a
helper exit of 3 (`EXTRACT_FAILED`) — exactly the outcome t2061 made the
procedure handle — kills the shell before `echo` runs, so the `DRIFT_RC:` line
the step-3 classifier depends on is never printed. The defect is real, so the
fix is option 1 from the task (rewrite into the guard's sanctioned
`if …; then rc=0; else rc=$?; fi` form, same as `build-verification.md`), not
an allowlist entry. The `DRIFT_RC:<rc>` output contract is preserved verbatim.

## Implementation

1. **`.claude/skills/task-workflow/remote-drift-check.md`** (authoring source),
   step 2 — replace both one-liners (keeping the 3-space fence indentation):

   ```bash
   if ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; then
     drift_rc=0
   else
     drift_rc=$?
   fi
   echo "DRIFT_RC:$drift_rc"
   ```

   and the same shape with `--unsynced "$output_branch" "<plan_file>"` for the
   output pass. Scanner rule (b) accepts a lone `drift_rc=$?` directly under
   `else`; `echo "DRIFT_RC:$drift_rc"` contains no `$?`.

   Adjust the sentence after the first block to say the trailing
   `DRIFT_RC:<rc>` line carries the run's exit status, captured in the
   `if`/`else` form so a non-zero exit (e.g. `EXTRACT_FAILED`'s 3) still
   reaches the line under `set -e` — still "not a protocol token". Step 3's
   `DRIFT_RC:0` / `DRIFT_RC:3` classification text is unchanged.

2. **`tests/test_task_workflow_reentry_drift.sh`** — the guard and negative
   control that pin the old spelling:
   - `drift-procedure-captures-exit-status` (≈line 332): count
     `echo "DRIFT_RC:$drift_rc"` in step 2 instead of `echo "DRIFT_RC:$?"`
     (still expects `2`).
   - its `negctrl` (≈line 444): break expr
     `s|echo "DRIFT_RC:\$drift_rc"|echo "DRIFT_BROKEN"|`, restore expr the
     inverse — so the control still proves the guard bites.

3. **Re-render tracked variants and the golden** (closure edit rule,
   `aidocs/framework/skill_authoring_conventions.md`):
   - tracked prerenders: `./.aitask-scripts/aitask_skill_render.sh task-workflow --profile remote --agent {claude,codex,opencode}` →
     `.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/`,
     `.opencode/skills/task-workflow-remote-/remote-drift-check.md`.
     Check `git status` afterward: the diff must be only `remote-drift-check.md`
     in each (anything else = unrelated staleness, leave it out).
   - golden: regenerate `tests/golden/procs/task-workflow/remote-drift-check-default.md`
     with the loop pattern in `tests/test_skill_render_task_workflow.sh`
     (`skill_template.py <proc> default.yaml claude`); review that the diff is
     exactly the two blocks + the sentence.
   - local (gitignored) default/fast renders refresh via `aitask_skill_render.sh`
     for completeness.

4. Step 9 (Post-Implementation): commit code (`bug: … (t2085)`), plan via
   `aitask_task_commit.sh`, archive.

## Verification

- `bash tests/test_skill_errexit_capture.sh` → 66/66.
- `bash tests/test_task_workflow_reentry_drift.sh` → all guards + negative
  controls pass (incl. the updated `drift-procedure-captures-exit-status` negctrl).
- `bash tests/test_skill_render_task_workflow.sh`,
  `bash tests/test_skill_parity_runtime_vs_rendered.sh`,
  `bash tests/test_remote_drift_check.sh`, `bash tests/test_plan_approved_marker_drift.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- Behaviour probe: in a scratch `set -e` shell, run the new block against a stub
  that exits 3 and confirm `DRIFT_RC:3` prints (and the old one-liner does not).

## Risk

### Code-health risk: low
None identified. (Doc-only procedure edit + one test's pinned spelling; render
outputs regenerated and diff-reviewed; tests pin the contract.)

### Goal-achievement risk: low
None identified. (The failing guard and the pinning test both run in
verification; the output contract `DRIFT_RC:<rc>` is unchanged.)

## Final Implementation Notes
- **Actual work done:** Rewrote both `DRIFT_RC` capture blocks in `.claude/skills/task-workflow/remote-drift-check.md` step 2 (base pass and `--unsynced` output pass) into the errexit-safe `if …; then drift_rc=0; else drift_rc=$?; fi; echo "DRIFT_RC:$drift_rc"` form, and extended the explanatory sentence with why the `if` form is used. Updated `tests/test_task_workflow_reentry_drift.sh`'s `drift-procedure-captures-exit-status` guard and its negative control to the new spelling. Re-rendered the tracked remote variants (`.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/`, `.opencode/skills/task-workflow-remote-/`) and the `remote-drift-check-default.md` golden.
- **Deviations from plan:** `aitask_skill_render.sh task-workflow` fails ("template not found: task-workflow/SKILL.md.j2") because task-workflow is a closure-only skill; rendering went through `aitask_skill_render.sh aitask-pick --profile <p> --agent <a>` instead, which re-renders the task-workflow closure. The diff was confined to the four `remote-drift-check.md` copies and the golden.
- **Issues encountered:** The task body named only line 27; the guard also flagged the identical output-pass line 42, and both were fixed.
- **Key decisions:** Took the task's option 1 (rewrite) over an allowlist entry, because the defect is real. A probe under `bash -e` with a stub that exits 3 showed the old one-liner exits before printing `DRIFT_RC`, while the new form prints `DRIFT_RC:3`. The `DRIFT_RC:<rc>` output contract is unchanged.
- **Upstream defects identified:** None
