---
priority: medium
effort: high
depends: [t1981_1, t1981_3]
issue_type: feature
status: Ready
labels: [task_relations, task-workflow, skills]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D8 in
full, and D11.**

This child is the consumer side, the reason the store exists. It covers:
- the hybrid notification model: pull by default, push narrowly;
- the pick-time "related work" check, and its re-run at the target's own Step 8;
- the Step 8e notify flow, with explicit analysis-completeness handling;
- `/aitask-note` with no target reading the store first.

Over-notification is a defect (premise 1). Every pushed note is a commit and a
push race. An incomplete or disabled analysis must **never** be presented as "no
affected targets".

It depends on t1981_1 (store) and t1981_3 (`analysis-state`). It does not wait
for t2192, except for the static fallback mode of the candidate generator
(t1981_2), which this child calls. Until t1981_2 lands, the fallback option
reports that it is unavailable.

## Neighbours (Reality check first)

- **t1663_4** adds a premise check to task-workflow Step 3 and plans it as
  "Check 6". Check 6 is already the `## Inbox` check. Whichever lands second
  takes the next number. Re-read Step 3 before editing.
- **t2192** upgrades `related-task-discovery.md` for `/aitask-note` (engine-based
  candidates). This child adds a "store first" step ahead of that procedure and
  owns Step 8e. Do not duplicate t2192's discovery changes.

## Scope

1. **The "related work" procedure file** (new, under
   `.claude/skills/task-workflow/`), run at two points.
   - **Step 3**: a check after Check 6. It hands the list to planning as
     context.
   - **The target's own Step 8**, before review: "related work during this
     implementation". It shows relations whose other side landed after the pick,
     and relations published after the pick-time check. A relation whose source
     already sent this task a note since the pick is marked "covered by note
     <id>" (checked through `aitask_query_files.sh inbox`). Display only.
   - Direction is stated on every row. The "landed since" group holds only
     edges from the landed task toward this one, or symmetric ones. The task's
     own outgoing edges are listed separately.
   - "Landed" means archived with status Done and no `archived_reason`.
     Superseded or obsolete archives are shown as "dropped".
   - Confirmation is **recomputed at read**: a landed task's impact bases are
     checked against its own `(t<L>)` commits, with the same function as Step 8e.
   - It shows freshness and confirmation, at most 8 items, and never blocks or
     writes.
   - The state lines are rendered in plain words: disabled, not analysed yet,
     analysed with 0 relations.
2. **`ait relations notify-candidates <S> [--diff <range>]`** (in
   `aitask_relations.sh`).
   - **The change set** is S's commits whose subject carries `(t<S>)`,
     reachable from HEAD: the task branch in worktree mode, the output branch in
     current-branch mode. `--diff` overrides it.
   - **Impact-only confirmation.** A `path` must be in the changed files (`-M`
     rename map included); a `symbol` or `token` must be in the diff hunks. A
     `task_ref` never confirms impact.
   - **The direction guard.** `affects` pushes only when `from = S`, with the
     recipient `to`. `coordinates_with` uses either endpoint.
   - **PUSH rows** only when all of these hold:
     - the type is `affects` or `coordinates_with`;
     - an impact basis is confirmed;
     - the target is Implementing or holds a plan;
     - the target's **current** body or plan still cites a confirmed basis.

     A target that has moved away from the surface gets PULL with
     `reason=target_moved`.
   - **Everything else connected is a PULL row**: `unconfirmed_impact`,
     `target_moved`, other types, other target states. Nothing is discarded.
3. **Step 8e** in `.claude/skills/task-workflow/SKILL.md`.
   - Call `analysis-state` first.
   - On `complete`, offer notes for PUSH rows: a multi-select, never
     automatic, each pre-filled with the stored description and the matched
     diff evidence. Before offering, the agent checks that the description still
     matches what landed.
   - On any incomplete state, state it, then offer:
     - *run now and wait* (`analyze --now --wait`). It counts against the cap.
       At the cap, it needs a second explicit confirmation and `--over-cap`;
     - *static discovery fallback* (`UNCONFIRMED` rows judged by the agent);
     - *proceed with what exists*.
   - With nobody to answer, the profile key `relations_incomplete_action`
     (`ask` default / `wait` / `fallback` / `proceed`) picks the option; `wait`
     never over-caps. Add the key to `profiles.md` and the shipped profiles.
   - When disabled: say so, keep today's judgement offer, and offer the static
     fallback as an optional aid.
   - Judgement-based offers for findings relations cannot derive stay as they
     are.
4. **`/aitask-note` with no target** (`.claude/skills/aitask-note/SKILL.md`):
   read relations(sender) first, then the Related Task Discovery Procedure.
   - `aitask-qa` and `aitask-review` keep their judgement-based offers. With no
     target they route through `/aitask-note`.
   - `aitask-explore`, `aitask-fold` and `aitask-contribution-review` are not
     changed (D8).
5. **Ledgers for the retrospective (D13.3).** Local `pull.jsonl` and
   `notify.jsonl` under `<git-common-dir>/aitask-relations/`. Each row records:
   - the relation;
   - its freshness (`fresh` / `stale:*`);
   - its confirmation (`confirmed_impact` / `unconfirmed_impact`);
   - the outcome (sent / declined / shown);
   - for Step 8e, the analysis state and the option chosen.
6. **Goldens.** Regenerate them for every `.md.j2` or procedure change, and run
   `aitask_skill_verify.sh`.

## Key files

- `.claude/skills/task-workflow/SKILL.md` (Step 3, Step 8, Step 8e)
- the new procedure file
- `.claude/skills/aitask-note/SKILL.md`
- `.aitask-scripts/aitask_relations.sh`
- the goldens and tests

## Reference patterns

- Step 3 Check 6 (the Inbox check): a display-plus-bookkeeping check that never
  ends the workflow.
- `aitask_query_files.sh inbox`: for the "covered by note" marking.
- `lib/plan_paths.py`: path canonicalization for basis matching.

## Implementation plan

See `aiplans/p1981/p1981_5_relations_consumption.md`.

## Verification

Fixture records and fixture diffs:
- **Direction cases:**
  - forward-only: "S affects X" pushes to X when S lands;
  - reverse-only: "X affects S" never pushes when S lands, even with a shared
    basis in S's diff, and shows under "this task's own relations";
  - symmetric: `coordinates_with` pushes to the other endpoint, whichever end S
    is.
- **A task-ref-only relation** → PULL with `unconfirmed_impact`, never PUSH.
- **A target whose current plan no longer cites the basis** → PULL with
  `target_moved`.
- **Change-set derivation** from `(t<S>)` commits, in both current-branch and
  worktree mode.
- **Expected-identity cases:**
  - Step 8e passes `--expect-plan <relations_expected_plan>`;
  - a resumed session whose committed plan is newer than the visible stamp →
    `unverifiable(stamp_mismatch)`;
  - a missing variable → `unverifiable(no_expected_identity)`.
- **An unrelated landing** (the impact basis is not in the diff) → PULL.
- **Incomplete-analysis cases:** pending, failed, missing, and the **cross-host
  case**. A stage-2 record from an earlier approval plus a newer stamp written on
  another host must report `incomplete:inputs_mismatch`. A missing stamp or a
  stale store read must report `unverifiable`. None of them may yield "no
  affected targets".
- **Disabled wording** at all four surfaces.
- **The Step 8 re-check** shows a relation published after the pick, and marks
  one already covered by a note.
- **Goldens** regenerated.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_1** id=2026-11-07T16:11:09Z.e9c8bf8a1c5e86d4c817ca21 from=t1981_1 from_verified=yes at=2026-11-07T16:11:09Z base=f78e2b8d59718a1e07660fef262bdf6477f09af2 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1981_1, the relations store (code commit f78e2b8d5). The read surface you will consume has states your plan may not render yet. The contract is in aidocs/framework/task_relations.md, D1 "Store API" and "Refs".
> | 
> | - `Store.relations(task, snap)` returns `Rel` with: `from_`, `to`, `other` (the endpoint that is NOT the queried task), `type`, `description`, `basis`, `evidence`, `record_task`, `direction` (prose such as "t12 affects this task" / "this task coordinates with t7"), `freshness` and `pending_push`. Use `other` for the machine-readable far end, never the direction prose.
> | - Freshness values: `fresh`, `stale:source_changed`, `stale:target_changed`, `unverified:source_baseline`, `unverified:target_baseline`. An unreadable baseline (corrupt bundle, another project's task) is `unverified`, never `fresh`.
> | - `ANALYSIS:` values, beyond D1's list: `unknown(other_project)` for a ref of another project. `unknown(store_unreachable)` remains "no data", which must never render as "no related tasks".
> | - Refs are qualified (`<project>#<id>`). The local project comes from `project.name`. A cross-project end keeps its qualification and is never canonicalized locally (D12).
> | - `ait relations show <id> [--json]` output starts with RELATIONS_STATE: / STORE: / ANALYSIS:. It can carry `CORRUPT:<path>|<reason>` lines; those blobs are excluded from the results. `--json` carries `project`, `task`, `analysis`, `store` and `relations[]` (each with `other`).
> | - STORE: states: `fresh@<ts>`, `stale:<reason>@<fetched_at|never>` (latest-known data is still served), `unreachable:<reason>`, `empty`, `local_only`.
> | - For notify-candidates (commit/diff confirmation), only impact bases (path/symbol/token) can confirm a relation. `task_ref` is connectivity only, and schema validation already enforces that affects / coordinates_with / supersedes carry an impact basis.
> | 
> | Read t1981_1's archived plan "Final Implementation Notes / Notes for sibling tasks" for the full list.
