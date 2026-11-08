---
priority: medium
effort: high
depends: [t1981_3, t1981_5]
issue_type: feature
status: Implementing
labels: [task_relations, backlog]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-08 18:14
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D9, plus
the parts of D2 that define the obsolescence record and the dismissal.**

This child is the second layer on the relations infrastructure. It gives
pending tasks an **obsolete score with reasons**: a band, cited evidence, and a
recommended disposition. It is **never auto-actioned** (premise 6). It shares
the store (t1981_1) and the worker and headless operation (t1981_3). It adds the
pick-time display of the band to the related-work check from t1981_5.

**Boundary with t1663 / t1655 (premise staleness).** Premise staleness ("needs
refresh") is theirs. Its verdict (`aitask_premise_stale.sh check`, when that
tool exists) is one evidence row here, and nothing more. This layer never
emits FRESH or ASK_STALE, and it shares no engine with them. If t1663_1 has not
landed, the row reads `premise: unavailable`.

## Scope

1. **`lib/obsolescence_evidence.py`** + `aitask_obsolete.sh evidence <id>`:
   static rows, tagged by kind.
   - `path_deleted` vs `path_renamed`: rename-aware `git log -M
     --diff-filter=DR`, cached per HEAD in `.aitask-cache/`, with suffix and
     relative resolution through `plan_paths`.
   - `origin_state`: whether the origin (`verifies` / `anchor` / follow-up
     origin) is archived, folded, deleted or reverted.
   - **A `## Revert Notes` reader** (the revert skill writes that section; no
     script reads it today).
   - `superseded_by` / `duplicate_of` / `affected_by_landed`: store relations.
   - `premise`.
   - `age`: a weak prior, labelled as such.
2. **The `obsolescence` operation prompt**:
   `.aitask-scripts/relations/prompts/obsolescence_assessment.md`. Output: band
   `none|low|medium|high`, reasons citing evidence ids, and a disposition
   (`keep|refresh|fold_into:<id>|drop`). If there is no row other than `age`,
   the band is `none` and no LLM runs.
3. **The worker job type** for `obsolescence`, writing `obsolescence/t<id>.json`
   with `evidence_digest`.
4. **The landed trigger** in `aitask_archive.sh` `main`, after the archive
   commit, **only for completed work**: status Done and no `archived_reason`.
   Superseded archives, obsolete archives and folded tasks fire nothing.
   Enqueue `obsolescence` for the pending tasks in relations(landed), and for
   the tasks whose origin is the landed task. It is silent and never fails the
   archive.
5. **`ait obsolete`**: `ls [--min-band]`, `show`, `dismiss <id> [--note]`,
   `review`, `sweep [--budget N]`.
   - A dismissal is keyed to `evidence_digest`, so the task resurfaces when the
     evidence changes.
   - `review` walks the list: open the task, fold it (the existing fold flow),
     archive it as obsolete, dismiss it, or skip.
6. **`aitask_archive.sh --obsolete`**, writing `archived_reason: obsolete`, next
   to the existing `--superseded`. Follow
   `aidocs/framework/aitasks_extension_points.md` for the frontmatter value, and
   update `website/content/docs/development/task-format.md`.
7. **The pick-time display**: show the task's own band, when it is medium or
   higher, in the related-work check (from t1981_5).

## Key files

- New: `lib/obsolescence_evidence.py`, `aitask_obsolete.sh`, the prompt, tests.
- Changed: `aitask_archive.sh`, `lib/relations_worker.py`, the related-work
  procedure, `website/content/docs/development/task-format.md`.

## Reference patterns

- `aitask_archive.sh --superseded` (`archived_reason: superseded`).
- `lib/followup_origin.py`: `exact` / `topic` / `unknown`.
- The seed's Appendix A.2 (`ait attach get 1981 task_relations_proposal.md`):
  the deleted-vs-renamed measurement.

## Implementation plan

See `aiplans/p1981/p1981_6_obsolescence_layer.md`.

## Verification

- A fixture repo with deleted, renamed and relative paths: the rows are
  correct.
- A reverted origin is detected from `## Revert Notes`.
- With only `age` evidence, the band is `none` and no agent is called.
- A dismissal hides the task until the evidence digest changes.
- `--obsolete` writes the reason.
- The landed trigger enqueues the related pending tasks and never fails the
  archive.
- `review` never acts without an explicit choice.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1663_1** id=2026-11-05T06:23:27Z.a939b74a47c0a100d9e92c9a from=t1663_1 from_verified=yes at=2026-11-05T06:23:27Z base=63f4478c0c38d097f3b632f7e8a655474dd197df base_branch=main dirty=yes host=omg16
>
> | From t1663_1 (the premise engine), landed in 306241f3d. Advisory context for your `premise` evidence row, which was waiting on "when that tool exists". It exists now.
> | 
> | `./.aitask-scripts/aitask_premise_stale.sh check <task_file>`, run from the code repo root, always exits 0 for content states. The record's protocol block is unchanged in shape: BASELINE / CHECKED / FINGERPRINT / FILES / CHANGED* / DELETED* / UNKNOWN* / DISPLAY / DECISION. The `DECISION:` vocabulary is unchanged: FRESH / ASK_STALE / SKIP.
> | 
> | Refinements versus the record as you read it:
> | - `CHECKED:NONE` (and `FINGERPRINT:NONE`) on SKIPs reached before the revision is pinned.
> | - Path fields encode LF and CR as well as `%` and `|`. Decode `%0D`, `%0A`, `%7C`, then `%25`.
> | - The closed SKIP and UNKNOWN reason vocabularies live in `lib/task_premise.py`. New values include `invalid_baseline`, `invalid_frontmatter`, `scope_error`, `history_unavailable` and `malformed_row`.
> | 
> | Today almost every task reads SKIP (`no_stored_baseline`), because baselines are only seeded once t1663_2/t1663_3 land.

> **👁 note:read** id=2026-11-08T16:14:26Z.026d6ca0c90a189af83237ab by=t1981_6 at=2026-11-08T16:14:26Z mode=explicit ids=2026-11-05T06:23:27Z.a939b74a47c0a100d9e92c9a

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T20:29:54Z status=pass attempt=1 type=human
