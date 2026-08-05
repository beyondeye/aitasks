---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [trails, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-05 12:33
updated_at: 2026-08-05 18:07
completed_at: 2026-08-05 18:07
---

## Problem

A trail's staleness check cannot see the two frontmatter fields that record
*post-landing* task connections, and the refresh procedure has no other way to
find them — so the follow-ups a member spawns as it lands are structurally
invisible to the one flow that runs after it lands.

Found while running `/aitask-trail --refresh art:trail-shadow-review-loop`
(2026-08-05). Four members landed between 2026-08-02 and 2026-08-05. Two of them
spawned live Step 8d risk-mitigation follow-ups — t1426 from t1293, t1411 from
t1319 — and neither surfaced as drift. They were found only because the agent
chose to read the archived members' `risk_mitigation_tasks:` frontmatter by hand;
nothing in the procedure asks for that.

## Two defects, one symptom

### 1. The gatherer reads only two connection edges

`new_related_task` fires on exactly two conditions
(`.aitask-scripts/lib/trail_gather.py` docstring `:74-77`, implemented at
`:937-943`):

- the task's qualified topic key matches an entry in the trail's `scope.topics`
- its `depends` intersects the persisted member set

`_canonical_depends` (`:383`) is the only relation the scanner normalizes. Two
structured frontmatter fields that encode real, machine-readable task
connections are never read anywhere in the module:

- **`risk_mitigation_tasks:`** — written at task-workflow Step 8d, the
  "after" follow-ups created *because* a task landed with a recorded residual
  risk. Present on archived t1293 (`[1426]`) and t1319 (`[1411, 1410]`).
- **`verifies:`** — the manual-verification back-reference. Note this one is
  partially masked today: t1425 (`verifies: [1293]`) *did* surface, but only
  because it happens to also carry `depends: [1293]`. A manual-verification
  task created without the depends edge would be invisible.

Both are the same class of deterministic, structured scan as `depends` — no
free-reading, no heuristics, no board access. They fit the gatherer's existing
contract rather than stretching it.

### 2. The skill's refresh flow has no candidate source but the scan

The create and refresh flows are asymmetric:

- **Create** (`.claude/skills/aitask-trail/SKILL.md.j2` Step 2c) has the agent
  read member task files and propose scope expansion from anything it finds
  there. Discovering a `risk_mitigation_tasks` pointer is possible.
- **Refresh** (Step 3.3) says: "New related tasks (**from `new_related_task`
  reasons**) are evaluated for membership." Candidates come *only* from the
  deterministic scan.

So the flow that runs after tasks land — exactly when Step 8d follow-ups and
manual-verification tasks are born — is the flow that stops looking for them.
Fixing the gatherer alone would close most of this, but the procedure should not
depend on the scanner being exhaustive.

## Required

1. **Gatherer: two new `new_related_task` edges.** A live task whose
   `risk_mitigation_tasks:` or `verifies:` intersects the persisted member set
   (stored task inputs + entry tasks — the same member set the `depends` edge
   already uses) is a related task. Normalize both to canonical refs, reusing
   `_canonical_depends`'s owning-project semantics rather than open-coding a
   second normalizer.

   Direction matters and must be decided explicitly: `depends` points *from* the
   new task *to* the member, and both new fields point the same way
   (`t1426.risk_mitigation_tasks` is absent — it is t1293, the **archived
   member**, that names 1426). So the member-side field is the one carrying the
   edge, and the member is usually *archived* by the time it matters. Confirm the
   scan reaches archived members' frontmatter, or invert the scan to read the
   member's own fields; do not assume the active-tree scan is enough. This is the
   part most likely to be got wrong — write the test first.

2. **Skill: an explicit re-read instruction in the refresh flow.** Step 3.3 gains
   a step: for every member that completed or was archived since the loaded
   version, read its `risk_mitigation_tasks:` and any `verifies:`
   back-references and evaluate those as membership candidates via the existing
   propose-and-confirm path. Keep it as a belt-and-braces instruction even after
   (1) lands — the procedure should not silently degrade if the scan misses a
   case.

3. Document both edges in the gatherer docstring's drift vocabulary (`:74-77`)
   and in `aidocs/implementation_trail_design.md` wherever the staleness contract
   is described.

## Explicitly out of scope

- **Task-file content hashing.** `INPUT:task_file` records carry no content hash
  while `plan_file` records do (`:29`), so a member's *prose* can change under a
  `CURRENT` verdict — this was also hit in the same refresh (t1159's scope was
  re-weighted by commit `bd6a10817` and the trail could not see it). Fixing that
  changes the input record, hence digest normalization, hence a
  `NORMALIZATION_VERSION` bump — which `SCHEMA_NORMALIZATION_LOCK`
  (`trail_gather.py:146`) requires to ship in lockstep with a `schema_version`
  bump. Materially larger and separable; propose as its own task if wanted.
- Widening `scope.topics` semantics. Not the fix, and actively harmful here: the
  trail that exposed this lists only one topic on purpose, because listing the
  members' three real topic roots would report every unrelated task in three
  large topics as drift forever.

## Verification

> **Corrected during implementation (2026-08-05).** The two bullets below
> originally described the `risk_mitigation_tasks` edge as running from a live
> task *to* an archived member. That is the wrong direction and contradicts §1
> of this task: real data has the **archived member** carrying
> `risk_mitigation_tasks: [1426]` while live t1426 has no back-reference. The
> original negative control was also **vacuous** — under a member-side scan
> nothing ever reads a live non-member's `risk_mitigation_tasks`, so the test
> would have passed without exercising any new code. Both are restated below.
> Direction confirmed with the user before implementation.

The discriminating test is a **negative control on the member set**, not a
happy-path scan: an **archived non-member** carrying
`risk_mitigation_tasks: [<live task>]` must NOT cause that task to be
reported, or the scan is walking the archive at large rather than intersecting
the persisted member set.

Also required:

- An **archived member** whose `risk_mitigation_tasks` names a live task is
  reported (the real case — t1293 names t1426, which carries no back-reference
  of its own).
- A manual-verification task with `verifies: [<member>]` and **no** `depends`
  edge is reported. Today's t1425 passes only via `depends`, so a fixture that
  keeps the depends edge would not prove the new code runs at all.
- The digest is unchanged by the new edges — they add drift *reasons*, not input
  records, so `DIGEST:` must not move. A trail that was `CURRENT` before the
  change and has no such follow-ups must still read `CURRENT`.
- `bash tests/run_all_python_tests.sh --test-dir tests` for the gatherer module;
  `./.aitask-scripts/aitask_skill_verify.sh` plus regenerated goldens for the
  skill change (`.md.j2` edit ⇒ regenerate in the same commit, per
  `aidocs/framework/skill_authoring_conventions.md`).

## Sequencing / coordination

- Per CLAUDE.md, make the skill change in the Claude Code tree
  (`.claude/skills/aitask-trail/`) first, then propose separate follow-up tasks
  for the Codex CLI (`.agents/skills/`) and OpenCode (`.opencode/skills/`) trail
  skills. Note that if the change lands only in the shared closure/`.md.j2`
  surface it may auto-render to the other agents — check before creating
  no-op follow-ups.
- The trail `art:trail-shadow-review-loop` (owned by t1159) records this defect
  from the consumer side in two observations, `obs-single-member-topic` and
  `obs-task-content-invisible-to-drift`. Refresh that trail after this lands so
  its recorded workaround ("read risk_mitigation_tasks by hand") stops being
  necessary — or is restated as a residual for the out-of-scope content-hash
  half.

Relevant sources: `.aitask-scripts/lib/trail_gather.py`,
`.aitask-scripts/lib/trail_schema.py`,
`.claude/skills/aitask-trail/SKILL.md.j2`,
`aidocs/implementation_trail_design.md`, `tests/test_trail_gather.py`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T14:14:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T15:00:30Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T15:07:44Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:84d095a80be1c04a

> **✅ gate:risk_evaluated** run=2026-08-05T15:07:44Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1429/risk_evaluated_2026-08-05T15:07:44Z-risk_evaluated-a1.log`
