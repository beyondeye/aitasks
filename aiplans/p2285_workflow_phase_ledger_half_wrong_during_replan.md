---
Task: t2285_workflow_phase_ledger_half_wrong_during_replan.md
Base branch: main
Output branch: main
---

# t2285 — Ledger half reads IMPLEMENT during a re-plan of a deferred approved plan

## Context

`workflow_phase.compose` falls back to the ledger half
(`phase_from_ledger_text` → `gate_ledger.resume_point_from_text`) whenever the
pane is not blocked on a question. If a task's `## Gate Runs` already has a
`plan_approved` pass, that half answers `IMPLEMENT`. So while the agent re-plans,
three consumers show IMPLEMENT when the agent is really planning:
- the full monitor's phase line (`monitor_app.py:2002`, `render_phase`);
- the minimonitor's narrow phase row;
- the shadow's advisory stamp (`MiniMonitorApp._restamp_shadow_phase` →
  `@aitask_shadow_phase`).

All three go through `GateSummaryCache.phase_for` → `_entry_for` →
`workflow_phase.phase_from_ledger_text(info.body)`
(`monitor/monitor_core.py:6061`). One fix in `phase_from_ledger_text` covers all
three.

**The original incident, checked against the real task data** (thinking_app
t587_5, in its `.aitask-data` history):
- 2026-11-10 18:04, `plan_approved` pass, attempt 1. At 18:08: "Revert t587_5 to
  Ready after plan approval", with **`plan_approved_at: 2026-11-10 18:08`**
  stamped (the deferred stop).
- 23:18, re-picked (`status: Implementing`). The marker was **still present**
  for the whole re-plan.
- 08:36, Step 7 recorded `plan_approved` attempt 2, and the next commit no
  longer had the marker. Step 7 clears it (`SKILL.md`, "implementation actually
  starting" → `--plan-approved-at ""`).

So the task text already holds the evidence the ledger half needs. The rule is:
**a `plan_approved` pass plus a live `plan_approved_at` marker means the approval
was deferred and implementation has not started.** That covers the re-plan
window exactly, from the re-pick to Step 7, and nothing more:
- The marker is stamped only by the `deferred` and `resource_admission` stops.
  The risk-mitigation "before" stop at `SKILL.md:657` keeps it.
- Every exit that starts implementation or invalidates the plan clears it: the
  Step 7 start, a create-from-scratch replan, abort, decomposition, and the
  drift/parallel stops.

The board already reads the same marker the same way
(`board/board_workflow_phase.py` §A, "Deferred-plan marker … status routes
first").

**Scope boundary (residual, see Risk).** Some re-plans clear the marker but leave
the recorded `plan_approved` pass in place. The task text then holds no re-plan
evidence, so this rule cannot see them, and they still read IMPLEMENT. There are
two such origins:
- the `drift`, `drift_check_failed` and `parallel_admission` stops
  (`plan-approved-stop.md`), which record the pass and then clear the marker;
- **planning.md §6.0-marker "Clearing on replan"**: every create-from-scratch
  branch (`create_new`, `ASK_STALE` → "Create plan from scratch", the
  interactive option) clears the marker before §6.1 and does not re-open the
  pass.

Both are the same defect: the approval is invalidated without that being
recorded in the ledger. They need the same workflow-side fix, so both are in the
agreed scope of the follow-up `replan_evidence_when_approval_invalidated`. Here
they are pinned by a regression case that documents the remaining behaviour
(test 10). The task's second candidate ("IMPLEMENT (ledger, unconfirmed)") would
not fix either: it changes only the rendered label, and the shadow stamp would
still carry `PHASE:IMPLEMENT`.

## Coordination — shared files (gate BEFORE the first edit)

`t2281` (Implementing, Codex questions) has **uncommitted** hunks in
`.aitask-scripts/lib/workflow_phase.py`, at the `_CODEX_QUESTION_HEADER_RE` and
`QUESTION_WIDGET_KINDS` lines (~123-200). It also has hunks in
`tests/test_workflow_phase.py`. My edit to `workflow_phase.py` (~325-338) does
not overlap, but a whole-file commit by either session would absorb the other's
hunks.

- **Do not edit `tests/test_workflow_phase.py`.** New tests go in a new file.
- **Do the non-overlapping work first** (steps 1, 3, 4, 5).
- **Gate for `workflow_phase.py` (step 2).** Immediately before the first edit,
  both checks must hold:
  - `git diff --quiet HEAD -- .aitask-scripts/lib/workflow_phase.py` (clean vs
    HEAD, staged and unstaged);
  - `git show HEAD:.aitask-scripts/lib/workflow_phase.py | grep -qF 'codex_mcp_form'`
    (t2281's hunk has really landed).

  After my first write, record its sha256, and re-check it (plus `HEAD:` blob
  unchanged and `git diff --cached --quiet -- <file>`) before every later write
  and before the commit.
- **If the gate still fails** when the other steps are done, stop and ask the
  user: wait for t2281, or agree on an explicit handover.
- Re-check `git diff --quiet HEAD -- <file>` for **every** other file at the
  moment of its first edit too. The session-start snapshot is not the gate.

## Implementation

### 1. `.aitask-scripts/lib/gate_ledger.py` — public named reader

Next to `read_active_gates_profile_from_text` (~line 1983), add:

```python
def read_plan_approved_at_from_text(text: str) -> str:
    """The deferred-plan marker (`plan_approved_at`, t1595), or ``""`` when the
    task carries none.

    **Supported cross-module API** (t2285): ``lib/workflow_phase.py`` uses it to
    tell a deferred approval (approved, implementation not started — the plan is
    being re-verified or re-planned) from one being implemented. A named reader
    for this one field, for the same reason as
    :func:`read_active_gates_profile_from_text`.
    """
    # Horizontal whitespace only: `\s` would cross the newline after a bare
    # `plan_approved_at:` and read the NEXT field as the marker.
    m = re.search(r"(?m)^plan_approved_at:[ \t]*(.*?)[ \t]*$",
                  _frontmatter_text(text))
    value = m.group(1).strip().strip("'\"") if m else ""
    return "" if value.lower() in ("null", "~") else value
```

- **Deliberately not `_read_frontmatter_scalar_from_text`.** Its `:\s*(.*?)\s*$`
  crosses line boundaries. Reproduced: frontmatter with a bare
  `plan_approved_at:` followed by `status: Implementing` returns
  `"status: Implementing"`, which would report PLAN during implementation.
  - The shared helper has 6 other callers, so the fix stays local, with no
    parser refactor.
  - The helper's defect is raised at Step 8b as an upstream-defect follow-up.
- It reads frontmatter only (`_frontmatter_text`), so a `plan_approved_at:` line
  in the body or the ledger cannot match.

### 2. `.aitask-scripts/lib/workflow_phase.py` — `phase_from_ledger_text` (GATED, see Coordination)

```python
    if not gl.has_gate_markers(text or ""):
        return UNKNOWN_PHASE, "no ## Gate Runs ledger recorded"
    phase = gl.resume_point_from_text(text)
    if phase == "IMPLEMENT":
        marker = gl.read_plan_approved_at_from_text(text)
        if marker:
            return ("PLAN",
                    f"ledger records plan_approved, but plan_approved_at "
                    f"({marker}) marks it deferred — implementation has not "
                    f"started, so the plan is being re-verified or re-planned")
    return phase, f"ledger checkpoints resolve to {phase}"
```

- Extend the docstring with one paragraph on the deferred-plan rule, and why it
  overrides only `IMPLEMENT`:
  - `POSTIMPL` needs `review_approved`, which only an implemented task has.
  - `PLAN` is already right.
  - No ledger stays `UNKNOWN`.
- **`gate_ledger.resume_point_from_text` is untouched.** It is the re-entry
  contract (`aitask_gate.sh resume-point`), and a deferred task is `Ready`, so
  Check 5 never reaches it anyway.
- The `|` in the detail is replaced at write time by `_sanitize`. The detail
  above contains none.

### 3. `tests/test_gate_ledger_public_api.py`

- Add `read_plan_approved_at_from_text` to `PublicSurfaceTest.REQUIRED`.
- Add `test_read_plan_approved_at_from_text_contract`:
  - `plan_approved_at: 2026-11-10 18:08` → that value;
  - absent, `""`, `null` and `~` → `""`;
  - a bare `plan_approved_at:` followed by `status: Implementing` → `""`.
    This is the regression case: at HEAD the shared helper reads the next
    field;
  - the same with trailing spaces (`plan_approved_at:   `), and with the bare
    key as the last frontmatter line → `""`;
  - a body-only `plan_approved_at:` line → `""`.
- The existing structural no-private-access check covers the new call
  automatically.

### 4. New `tests/test_workflow_phase_deferred_plan.py` (unittest, pure)

The fixtures are real task text in the t587_5 shape: frontmatter with `status`
and `plan_approved_at`, plus a `## Gate Runs` section with real markers. Tests:

1. `PLAN_RUN` + marker → `("PLAN", …)`, and the detail names `plan_approved_at`.
2. `PLAN_RUN` without a marker → `IMPLEMENT` (unchanged).
3. `PLAN_RUN` + `plan_approved_at: ""` → `IMPLEMENT`.
4. `PLAN_RUN` + `REVIEW_RUN` + marker → `POSTIMPL` (only IMPLEMENT is overridden).
5. No ledger + marker → `UNKNOWN` (no-ledger stays unknown).
6. The marker only in body prose or the ledger area → `IMPLEMENT`.
6b. `PLAN_RUN` + a bare `plan_approved_at:` directly above `status:
    Implementing` → `IMPLEMENT` (an empty marker never reads as deferred).
7. **Incident timeline through `phase_signal`** (agent `claude`):
   1. awaiting input, kind `claude_plan_approval` → PLAN/`native-prompt`;
   2. running (`awaiting_input=False`) → **PLAN/`ledger`** (pre-fix:
      IMPLEMENT);
   3. after Step 7 (attempt-2 block appended, marker removed), running →
      IMPLEMENT/`ledger`.

   `render_phase` / `render_phase_narrow` of the step 2 signal read `phase: PLAN`
   and `PLAN`.
8. **Monitor consumer** — `GateSummaryCache.phase_for` over a real temp task
   file, using the `tests/test_monitor_gate_cache.py` idiom (`_task_text` /
   `_info`):
   - with the marker → PLAN/`ledger`;
   - rewrite the file without the marker (mtime/size change) → IMPLEMENT.

   This proves the cache invalidates on a frontmatter-only edit. The cache's
   ledger *identity* (t2283) must still be unchanged by that edit. Assert that
   too: it is what keeps the t2283 banner from retiring on a marker clear.
9. **Shadow-stamp wire format.** `format_signal` → `parse_signal` round trip of
   the step-2 signal keeps `PHASE:PLAN` / `SOURCE:ledger`. That is the value
   `_restamp_shadow_phase` writes.
10. **Residual, pinned (documents remaining behaviour).**
    `test_marker_cleared_replan_still_reads_implement`, with one subtest per
    origin:
    - "create-from-scratch replan (planning.md §6.0-marker clear)";
    - "drift / parallel-admission stop".

    Each subtest uses task text in the exact shape that origin leaves:
    - `status: Implementing`;
    - the `plan_approved` pass (attempt 1);
    - no `plan_approved_at` key, because `aitask_update.sh --plan-approved-at ""`
      removes it.

    Each asserts `phase_signal(..., awaiting_input=False)` →
    `IMPLEMENT`/`ledger`. The docstring says this is the known gap, names the
    follow-up `replan_evidence_when_approval_invalidated`, and says the
    assertion must flip to PLAN when that follow-up lands. That way the gap
    cannot close, or widen, silently.

### 5. Docs — `aidocs/framework/shadow_agent.md`

- **"### The signal", source 3 (the ledger).** Add: an `IMPLEMENT` answer is
  downgraded to `PLAN` while the task carries the `plan_approved_at`
  deferred-plan marker. The approval was deferred, and the marker is cleared the
  moment implementation starts, so the window is exactly a re-verify or
  re-plan. Name the residual: a re-plan whose approval was invalidated by
  clearing the marker still reads `IMPLEMENT`. That covers a create-from-scratch
  replan (planning.md §6.0-marker) and a re-plan after a drift or
  parallel-admission stop.
- **"Why a ledger-derived phase must bring new evidence"** (~line 546). This
  paragraph currently says the ledger "reads `IMPLEMENT` for the whole time the
  agent works the feedback". Reword it to current state:
  - under a deferred plan the ledger half now reads `PLAN`, so it matches the
    origin phase and cannot retire;
  - after a marker-clearing invalidation (a create-from-scratch replan, or a
    drift or parallel stop) it still reads `IMPLEMENT`, and the
    content-identity rule is what keeps the banner up.

  Both rules stay. Current state only, no version history.

## Verification

- `python3 -m pytest tests/test_workflow_phase_deferred_plan.py tests/test_gate_ledger_public_api.py -q`
- Neighbouring suites:
  - `tests/test_workflow_phase.py`
  - `tests/test_monitor_gate_cache.py`
  - `tests/test_shadow_phase_restamp.py`
  - `tests/test_minimonitor_concern_action.py`
  - `tests/test_minimonitor_gate_phase_row.py`
  - `tests/test_monitor_gate_summary.py`
  - `tests/test_gate_ledger_only_surfaces.py`
  - `tests/test_board_workflow_phase.py`
- Shell suites: `tests/test_workflow_phase_standalone.sh`,
  `tests/test_gate_workflow_phase.sh` and `tests/test_shadow_phase_advisory.sh`.
- **Red proof** in a detached scratch worktree at HEAD
  (`git worktree add --detach <scratchpad>/base HEAD`). Copy in only the new
  test file and run it there. Then classify every assertion:
  - must fail at baseline: tests 1, 7.2, 8 (marker case) and 9;
  - must pass at baseline (regression guards): 2-6, 6b, 7.1, 7.3 and 10;
  - the public-API tests error on the missing reader.

  Separately, a **mutant** of the new reader that delegates to
  `_read_frontmatter_scalar_from_text` must fail the bare-key regression cases
  (public-API bare key, test 6b). This proves those cases discriminate.

  Then remove the worktree. No stash or restore in the shared tree.
- Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh`. Read the
  last line only, and attribute any failure to this change or not.
- `shellcheck` is not affected (no shell edits).

## Post-implementation

Step 9: commit by path only (`gate_ledger.py`, `workflow_phase.py`, the two test
files and `shadow_agent.md`) as
`bug: Read a deferred approved plan as PLAN in the ledger half (t2285)`, then
archive through the standard workflow.

- **Step 8b upstream defect.** `gate_ledger._read_frontmatter_scalar_from_text`
  reads the next field for a bare key, because `:\s*` crosses the newline. This
  was reproduced in planning. Offer a follow-up that audits its 6 callers and
  fixes the helper.
- **Step 8d.** Create the spawned "after" mitigation
  `replan_evidence_when_approval_invalidated`.

## Risk

### Code-health risk: low
- `workflow_phase.py` has t2281's uncommitted hunks. A whole-file commit by
  either session would absorb the other's change · severity: low · the
  Coordination gate (clean vs HEAD + handover grep before the first edit,
  sha-chain after it) prevents it · → mitigation: none
- A new public reader in `gate_ledger` widens the surface `workflow_phase`
  depends on · severity: low · it is pinned by `test_gate_ledger_public_api.py`,
  the same pattern as the two existing named readers · → mitigation: none

### Goal-achievement risk: medium
- A re-plan whose approval was invalidated by **clearing the marker** still
  reads IMPLEMENT. Origins: planning.md §6.0-marker's create-from-scratch clear,
  and the `drift` / `drift_check_failed` / `parallel_admission` stops. Each
  leaves the `plan_approved` pass with no re-plan evidence in the task text
  · severity: medium · the observed incident (deferred stop → verify re-plan) is
  fully covered, and test 10 pins the remaining behaviour. Closing the gap
  needs a workflow-side change (the invalidating write leaving durable "approval
  must be re-verified" evidence), which this task does not own · → mitigation:
  replan_evidence_when_approval_invalidated
- The new reader could misread an empty marker. The shared
  `_read_frontmatter_scalar_from_text` crosses lines, as reproduced
  · severity: low · the reader uses its own horizontal-whitespace regex, with
  bare-key regression cases and a delegating mutant · → mitigation: none
- A marker that outlives the start of implementation would show PLAN during
  implementation. This could come from a hand edit, or a future stop path that
  forgets to clear it · severity: low · Step 7 clears it unconditionally, the
  signal is advisory (one extra keystroke at most), and the board already
  trusts the same marker · → mitigation: none

### Planned mitigations
- timing: after | name: replan_evidence_when_approval_invalidated | type: bug | priority: low | effort: medium | inline_risk: high | added_complexity: medium | addresses: a re-plan whose approval was invalidated by clearing plan_approved_at (planning.md §6.0-marker create-from-scratch clear; drift / drift_check_failed / parallel_admission stops) still reads IMPLEMENT in the workflow-phase ledger half | desc: Make every marker-clearing invalidation leave durable task-text evidence (e.g. re-open plan_approved as task-abort.md does, or a distinct marker) that workflow_phase's ledger half reads as PLAN; flip t2285's test_marker_cleared_replan_still_reads_implement to PLAN
