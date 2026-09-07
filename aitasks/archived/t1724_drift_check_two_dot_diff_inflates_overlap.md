---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [backend]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-07 09:00
updated_at: 2026-09-07 16:40
completed_at: 2026-09-07 16:40
---

`aitask_remote_drift_check.sh:211` computes the remote-changed file set with a
**two-dot** `git diff`:

```bash
remote_files=$(git diff --name-only "${BASE_BRANCH}..origin/${BASE_BRANCH}" 2>/dev/null) || remote_files=""
```

**Two-dot means different things in `git log` and `git diff`.** In `git log`,
`A..B` is a commit range ("commits in B not in A"). In `git diff` it is treated
the same as `git diff A B` — a plain endpoint-to-endpoint comparison. So this
line reports every file that differs between the two branch tips, **including
files changed only by the user's own local commits**, not the files the remote
actually changed.

The correct form for "what the remote added" is **three-dot**
(`git diff --name-only A...B`), which diffs from the merge base.

## Measured live (2026-09-06, this repository)

| form | files reported |
|---|---|
| `git diff --name-only main..origin/main` (current) | **78** |
| `git diff --name-only main...origin/main` (correct) | **9** |
| `git log --oneline main..origin/main` | 2 commits |

The check reported `OVERLAP:tests/test_trail_gather.py` against a plan that
referenced that file. The remote commits (`24f8d010b`, `3160b7d4b`) **do not
touch it** — it was changed by the user's own local commits `a9f09daea` (t1647_2)
and `87245845b` (t1698).

## Why it matters

`OVERLAP` is the **strong** half of the drift check — it is always treated as
strong regardless of the `warn` / `strong-only` setting, and it is the branch
that interrupts the user immediately before implementation. Inflating it with
the user's own landed work is the "cry wolf" failure the procedure's own
`FETCH_FAILED` note warns about: a guard that fires on non-events trains the
user to click past it, and the real overlap it exists to catch then goes past
too.

The `AHEAD:<n>` count is derived separately and was correct (2), so the
symptom is a **mismatch between the commit count and the file list** — which
also makes the bug hard to notice by eye.

## Scope

1. Change `:211` to the three-dot form.
2. Check for the same two-dot-in-`git diff` confusion elsewhere in the
   framework — this is a general foot-gun, not a one-site typo.
3. Add a regression test with a fixture repo where the local branch has its own
   commits touching a file the remote never touched, and assert that file is
   **not** reported as `OVERLAP`. Without the local-only commit the fixture
   passes under both forms and proves nothing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-07T13:28:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-07T13:34:14Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-07T13:40:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3b9f757900e555c1

> **✅ gate:risk_evaluated** run=2026-09-07T13:40:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1724/risk_evaluated_2026-09-07T13:40:39Z-risk_evaluated-a1.log`
