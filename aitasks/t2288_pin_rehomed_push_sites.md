---
priority: medium
effort: medium
depends: [1912_3]
issue_type: test
status: Ready
labels: [git, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-11-12 19:43
updated_at: 2026-11-12 19:43
---

## Context

This is the 'after' risk mitigation of t1912 (planned mitigation
`pin_rehomed_push_sites`; see the `## Risk` section of
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`). It depends on
**t1912_3** (`rehome_task_data_publication`).

In t1912, the stats writers stop converging `aitask-data`. Their converge
used to push unpushed task-data commits as a side effect. t1912_3 replaced
that with an explicit best-effort `./ait git push` at each session-ending
step that relied on it:

- task-workflow Step 9 "Defer — keep in-flight";
- child-split "Stop here";
- cross-repo "Stop here";
- explore "save for later";
- aitask-qa Step 7;
- aitask-docs-gap;
- aitask-add-model;
- aitask-refresh-code-models;
- plus anything t1912_3 added.

The inventory came from grep. The risk is a missed path, or a new stop exit
added later without a push: either silently stops publishing task data.

## Goal

Add a pinned-inventory guard test, in the style of
`tests/test_metadata_writer_inventory.py`. It must make four independent
assertions, each able to fail:

1. **Every pinned site still exists.** Pin by skill file + step anchor text,
   not line numbers.
2. **Each pinned site has an explicit `./ait git push`** after its last
   task-data commit and before its end/stop banner, in the rendered variants
   (fast/default/remote, using the goldens under `tests/golden/`).
3. **Discovery tripwire.** A new "Stop here" / end-banner exit that follows
   a task-data commit (`aitask_task_commit.sh`, `aitask_create.sh --commit`,
   `./ait git commit`) with no push fails until it is classified: pinned, or
   exempt with a stated reason.
4. **The discovery patterns still find the known sites.** Otherwise (3)
   could pass by finding nothing.

Read first:
- the archived t1912_3 plan, for the final site list;
- memory/feedback about static guards (inventory = guard regex,
  tracked-only selection).

## Verification

The test passes on the tree. Mutation check: deleting one push from a
pinned site fails assertion 2; adding a synthetic unpushed stop exit fails
assertion 3. Record both in the plan's notes.
