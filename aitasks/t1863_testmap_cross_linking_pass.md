---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [testmap, task-planning, dependencies]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-22 17:32
updated_at: 2026-09-22 17:32
---

## Origin

Risk-mitigation ("after") follow-up for t1852, created during t1852's coarse
planning pass (2026-09-22) rather than at Step 8d, because that pass stopped
at the child checkpoint and would never have reached Step 8d. Recorded in
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md` under
`### Planned mitigations` as `testmap_cross_linking_pass`.

## Risk addressed

goal-achievement — cross-parent edges named by the wrong child number.
From the t1852 plan's `## Risk` section: "Cross-parent edges (M2.1 / M2.3 /
M3.1 / M5.1 / M6.1 → M1 children) are written by other parents' passes; if a
later pass names a child by the wrong number, the graph silently unblocks work
early."

## Goal

The test map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`)
is ten parent tasks t1852–t1861, one per module, each decomposed at its own
coarse planning pass into one child per submodule row. Cross-module order is
expressed in task data: a child's `depends:` names the children of other
parents it consumes, in `t<parent>_<m>` form. This task is the **one
cross-linking pass** the parents' bodies prescribe "after all ten parents are
planned": it checks every "depends on" cell against a real `depends:` entry,
checks the module → task map in every parent body against the real parent
ids, then refreshes the trail `art:trail-testmap-feature` with `--deep`.

Passes run in wave order at submodule granularity (M1's children are
implemented before M2 is planned), so by the time the last pass lands, early
children are **archived**. This task treats archived records as complete
evidence and repairs only pending tasks.

### Step 0 — completeness precondition (all-or-nothing, before any write)

`aitask_query_files.sh has-children` proves nothing here: it succeeds on any
positive local file count, and `children_to_implement` grows incrementally
during creation, so an interrupted or in-progress pass looks "decomposed".
Validate every prescribed submodule of every parent instead:

- For each parent t1852–t1861, resolved from **active or archived** records
  (`./.aitask-scripts/aitask_query_files.sh resolve <id>`, else
  `archived-task <id>`; `aitask_archive.sh` moves a finished parent and its
  children to `aitasks/archived/t<parent>/` and `aiplans/archived/p<parent>/`),
  parse its `## Submodules` table for the `**M<n>.<m>**` rows.
- For every row **not** marked `(cross-repo)`: require exactly one child file
  whose stem carries `m<n>_<m>_` across `aitasks/t<parent>/` and
  `aitasks/archived/t<parent>/`, **and** its plan file —
  `aitask_query_files.sh plan-file <parent>_<k>` (active) else
  `aiplans/archived/p<parent>/p<parent>_<k>_*.md` — containing the
  `Step 0 — Reality check` heading. An archived child with its archived plan
  is complete evidence (a landed provider), never `INCOMPLETE`.
- For every row marked `(cross-repo)` (today M10.2–M10.5 in t1861): require
  the parent's plan file to carry the cross-repo decomposition record
  (`.claude/skills/task-workflow/planning-cross-repo.md` Step 6: the
  `label | side | nominal parent | in-repo deps | cross-repo deps` table)
  with one entry naming that row and its target project as registered in
  `ait projects list`.
- Any missing item → print `INCOMPLETE:t<parent>:M<n>.<m>:<reason>` for each,
  then **stop with no dependency writes**; re-pick when the remaining passes
  have landed.

### Step 1 — graph check and repair, pending local rows only

For every local row whose child is **pending** (active and not `Done`):
check each "depends on" cell of the parent's submodule table against a real
`depends:` entry in `t<parent>_<m>` form on that child, and fill only the
missing ones with `./.aitask-scripts/aitask_update.sh --batch <child> --deps
"<current + missing>"` (`--deps` **replaces** the list — read it first).
Archived or `Done` children are **never** updated: a landed provider's edges
are history, and a dependency *on* an archived child is already satisfied,
so it is neither added nor required.

**M10.2–M10.5 are never repaired with local ids.** They live in their target
repositories, are referenced with `<project>#<id>` notation
(`aidocs/framework/cross_repo_references.md`), and depend on the framework
release carrying M1–M9 reaching each target rather than on this repository's
task ids (t1861 body). For them, only check that the cross-repo record names
each row and that any already-created cross-repo task carries the
project-qualified reference (`xdeps` + `xdeprepo`, both-or-neither);
mismatches are **reported, never rewritten** from here.

Then check the module → task map in every parent body against the real
parent ids, and refresh the trail:
`/aitask-trail --refresh trail-testmap-feature --deep`.

`depends: []` on purpose — a `depends:` on the parents would block this task
until they are *Done*, far too late; Step 0 is the real gate.

## Verification

- Dry run first: print every `INCOMPLETE:` / mismatch line before any write.
- After repair, `./.aitask-scripts/aitask_ls.sh -v --children <parent> 99`
  for every parent shows blocked/unblocked exactly per its submodule table.
- The refreshed trail lists child tasks grouped by wave.
