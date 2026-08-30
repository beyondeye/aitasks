---
Task: t1640_clear_plan_approved_at_on_single_repo_decomposition.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1640 — Clear `plan_approved_at` on single-repo decomposition

## Context

`plan_approved_at` marks a task whose plan was approved and whose
implementation was **deliberately deferred** ("Approve and stop here"). Its
contract is: the marker is true only while an approved single-task plan is
still awaiting implementation. Every site that ends that state must clear it.

One site does not. `.claude/skills/task-workflow/planning.md:281` — the
single-repo decomposition cleanup — reverts the parent with
`--status Ready --assigned-to ""` but omits `--plan-approved-at ""`. Its
cross-repo twin (`cross-repo-child-assignment.md:115`) *does* clear it, and its
own comment says it is "mirroring the single-repo decomposition cleanup" — so
the two sites disagree by their own description. The cross-repo rationale
(`:119`, "this task's single-task plan no longer describes implementable work")
is the one that holds: after decomposition the parent's single-task plan has
been replaced by the children, so the marker lies.

Reachable path: approve-and-stop → re-pick → §6.1 assesses complex → children
created → parent keeps the marker and renders `📋 Planned` on the board while
its plan describes work the children replaced. t1603_1 renders that state
deliberately (the board is a read-only mirror; showing it is what makes the
staleness visible) and pins it with
`test_a_parent_with_an_implementing_child_still_surfaces_planned` — fixing the
workflow was explicitly out of scope there.

Deliberate **non**-clear that must survive untouched: the risk-mitigation
"before" stop at `task-workflow/SKILL.md:551`. That plan is *blocked*, not
invalidated — approved and still awaiting implementation, which is exactly what
the marker means. It already carries a comment saying so.

## Changes

### 1. The fix — `.claude/skills/task-workflow/planning.md` (~line 281)

In the Complexity Assessment "revert the parent" step, append the flag:

```bash
./.aitask-scripts/aitask_update.sh --batch <parent_num> --status Ready --assigned-to "" --plan-approved-at ""
```

Add the rationale prose immediately below the existing "Has children" sentence,
worded as at the cross-repo site (no-op when the task never carried a marker),
plus a reciprocal pointer naming `cross-repo-child-assignment.md` Step 4 so a
future reader does not "fix" one back.

### 2. The twin — `.claude/skills/task-workflow/cross-repo-child-assignment.md` (~line 119)

Add the reciprocal half of that pointer to its existing rationale paragraph,
naming `planning.md`'s Complexity Assessment. Neither site's semantics change;
this just makes the pair self-documenting in both directions.

### 3. Falsified claims — every clear-site enumeration

Adding a clear site falsifies every prose enumeration of when the marker is
cleared. These were found by an **identity-anchored** sweep (grep the marker's
own names — `plan_approved_at`, `deferred-plan`, `Plan: approved`,
`--plan-approved` — then read each hit), *not* by guessing at phrasings: each
of the five sites words the lifecycle differently, so a phrase-based sweep
silently misses some. This is the complete set — all five, and each already
omits the cross-repo demotion too, so one phrase repairs both gaps at once:
**"when the task is decomposed into children"** covers the single-repo and
cross-repo sites alike.

User-facing:

- `.claude/skills/aitask-pick/SKILL.md.j2:177` — "…cleared when implementation
  starts, on a replan, on an abort, and when a remote-drift stop demands
  re-verification".
- `website/content/docs/development/task-format.md:56` — the `plan_approved_at`
  row: "…cleared when implementation starts, on a replan or abort, and when a
  remote-drift stop demands re-verification".
- `website/content/docs/commands/task-management.md:120` — the "Deferred
  approved plans" paragraph: "…cleared as soon as it stops being true —
  implementation starts, the plan is replanned or aborted, or a remote-drift
  stop requires re-verification".

Canonical references in `aidocs/` — the ones a future reader and the contract
test's own rationale are pointed at, so stale here is worse than above:

- `aidocs/framework/aitasks_extension_points.md:269` — the `plan_approved_at`
  worked example's lifecycle bullet names planning.md's clear as "`planning.md`
  §6.0's replan branches". Widen it to name the §6.1 decomposition cleanup as
  well, so the bullet still lists every site the contract test is expected to
  pin. (The "across five procedure files" count is unchanged — the new site is
  in `planning.md`, already listed.)
- `aidocs/gates/ledger-driven-reentry.md:219` — the lifecycle table has a
  `Cross-repo demotion to parent-of-children | cleared` row but none for
  single-repo decomposition. Generalize that row to cover both
  ("Decomposition into children (single-repo or cross-repo)"), which also makes
  the twinning explicit at the canonical table rather than only in the two
  procedure files. The adjacent `Risk-mitigation "before" stop | retained` row
  stays exactly as-is — it is the table's half of the boundary.

**Checked and deliberately not changed:** `AGENTS.md:32` and
`seed/aitasks_agent_instructions.seed.md:31` mention the marker but say only
"Set/cleared by the workflow only" — no enumeration, so nothing is falsified.
`tests/test_plan_approved_marker_drift.sh` is a behavioral test of the drift
path, not a doc-drift guard.

### 4. The guard — `tests/test_plan_approved_marker_contract.sh`

This file already exists as the executable guard for the marker's lifecycle and
already pins the **retain** direction (the mitigation stop's plain revert, its
deliberate-omission note, and the "exactly one marker-clearing command in fast
`SKILL.md`" count). Add the missing **clear** direction so the pair is complete:

- In "The clear sites": assert the decomposition site renders the clear in
  **every** profile render (`default`, `fast`, `remote`), needle
  `--batch <parent_num> --status Ready --assigned-to "" --plan-approved-at ""`,
  count `1`.
- Extend the file's header comment to note that `planning.md` now carries two
  clear sites (replan and decomposition) and that the decomposition assertion is
  the counterpart to the mitigation-stop absence check.

The needles do not collide: the replan clear is matched on
`--plan-approved-at "" --silent`, the decomposition clear uses `<parent_num>`,
the cross-repo clear uses `<current_task_id>`, and the mitigation-stop boundary
check greps `SKILL.md` for `<task_num>`.

### 5. Regenerated artifacts (same commit)

- Procedure goldens: `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`
  and `cross-repo-child-assignment-default.md`.
- Entry-point goldens: `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md`.
- Live rendered closures: `./.aitask-scripts/aitask_skill_rerender.sh <profile>`
  for `default`, `fast`, `remote` — it loops `claude`/`codex`/`opencode`, so the
  Codex and OpenCode trees (thin stubs that render from these same canonical
  templates) are covered with no separate port task.

Regeneration uses the documented loop in
`aidocs/framework/skill_authoring_conventions.md` ("Regenerate goldens after any
`.md.j2` or closure edit"). Review the golden diff — it must contain only the
edited lines.

## Out of scope (deliberate)

- `task-workflow/SKILL.md:551` — the risk-mitigation "before" stop keeps the
  marker. Not touched.
- `crash-recovery.md:141` — declining a reclaim reverts to `Ready` without
  invalidating the plan; the marker correctly survives.
- `aitask-revert/SKILL.md.j2` — reverts a `Done` task, which cannot carry a
  marker.

## Verification

```bash
bash tests/test_plan_approved_marker_contract.sh     # both directions
bash tests/test_skill_render_task_workflow.sh        # procedure goldens
bash tests/test_skill_render_aitask_pick.sh          # entry-point goldens
./.aitask-scripts/aitask_skill_verify.sh             # stub-surface integrity
bash tests/test_plan_approved_at_roundtrip.sh        # field writer unchanged
```

### Post-phase (risk mitigations)

- **negative-control-decomposition-clear** — with the fix reverted in the
  rendered `planning.md`, re-run `tests/test_plan_approved_marker_contract.sh`
  and confirm the new decomposition-clear assertion FAILS, then restore. This
  proves the assertion pins the actual defect rather than passing vacuously on
  a needle that never matched.
- **enumeration-sweep-recheck** — after the edits, re-run the **identity-anchored**
  sweep and confirm no lifecycle enumeration still omits decomposition. Anchor
  on the marker's own names, never on a phrasing — the five sites word the
  lifecycle five different ways, and a phrase pattern that fits four of them
  passes while the fifth stays stale (exactly how
  `commands/task-management.md:120` was missed on the first pass):

  ```bash
  grep -rn "plan_approved_at\|deferred-plan\|Plan: approved\|--plan-approved" \
    --include=*.md --include=*.j2 --include=*.py --include=*.sh . \
    | grep -v "^./website/public/" \
    | grep -v -- "-default-/\|-fast-/\|-remote-/\|_skillrun_\|/tests/golden/"
  ```

  Read every hit rather than pattern-filtering it. Each must either (a) name
  decomposition among the clear sites, (b) make no lifecycle claim at all (the
  `AGENTS.md` / seed comments, the `ait ls` flag rows), or (c) be about a
  single specific event where the omission is correct (e.g.
  `plan-approved-stop.md`'s drift branch). The five sites listed in §3 are the
  expected (a) set — if the sweep turns up a sixth, it was missed, not new.

## Risk

### Code-health risk: low
- The change is one flag plus prose in a procedure file, with regenerated
  goldens. The one real hazard is a needle collision making a contract
  assertion vacuous; the four needles were checked as mutually exclusive
  above. · severity: low
  · → mitigation: inline post-phase negative-control-decomposition-clear
- Adding a clear site falsifies every prose enumeration of the clear sites, and
  those are spread across five files that each word the lifecycle differently.
  Two were missed on successive passes through this plan, both times because
  the sweep matched a phrasing instead of the marker's identity. A missed one
  leaves a doc telling the next reader the site does not exist.
  · severity: low · → mitigation: inline post-phase enumeration-sweep-recheck

### Goal-achievement risk: low
- None identified beyond the above — the task names the exact site, the exact
  flag, the twin to mirror, and the boundary not to sweep, and all four were
  confirmed by reading the files.

### Planned mitigations

- **negative-control-decomposition-clear** — inline post-phase, confirmed.
- **enumeration-sweep-recheck** — inline post-phase, confirmed.

Both specs are in "Post-phase (risk mitigations)" under Verification. No spawned
before/after tasks: both dimensions are `low` and both hazards (assertion
vacuity, an unswept enumeration) are settled by controls inside this task.
