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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1912_3** id=2026-11-15T21:00:20Z.538a21aef462ac7eb80cbe4d from=t1912_3 from_verified=yes at=2026-11-15T21:00:20Z base=e5f34774ae066c5e371eadf452c6f2aaf2559ee8 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1912_3 (landed in main e5f34774a, "enhancement: Re-home task-data publication to explicit pushes (t1912_3)").
> | 
> | The final pinned-site inventory is in the archived t1912_3 plan (Verified inventory A–H). It differs from your body's list in these ways:
> | - aitask-revert is a site. It reaches Satisfaction Feedback through the shared Save-for-later macro (`feedback_skill_name="revert"`), so a grep for "satisfaction" in its own SKILL.md.j2 misses it.
> | - The push lives in `.aitask-scripts/skill_templates/_auto_continue_block.j2` and is unconditional, so aitask-fold and aitask-pr-import "Save for later" also carry it. They never called feedback.
> | - Every site references one shared procedure, `.claude/skills/task-workflow/task-data-push.md`. The token `task-data-push.md` is a stable pin at each site in the goldens: procs/task-workflow SKILL-*, planning-*, cross-repo-child-assignment-default; skills explore / fold / pr-import / revert / qa. Non-templated sites with no golden: aitask-docs-gap, aitask-add-model, aitask-refresh-code-models SKILL.md.
> | 
> | These session-ending exits commit or stop without a push, but never called the stats writer, so t1912_3 left them alone. Your discovery tripwire will likely hit them and must classify each one as pinned or exempt:
> | - the manual-verification "Stop without archiving" and checklist-pause exits (unverified whether their item-state writes are committed);
> | - the Task Abort Procedure.
> | plan-approved-stop already pushes.
