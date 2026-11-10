---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [task_relations, documentation]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-10 11:41
updated_at: 2026-11-10 11:41
---

## Context

Child of t1981. The obsolescence layer (t1981_6) and the archive fix for an auto-archived parent's reason (t2254) have both landed. The website still has no user-facing explanation of obsolescence. The relations docs task t1981_8 covers it only as an `ait obsolete` CLI reference: its concept page is about relations, and its workflow pages cover the related-work check, Step 8e and `/aitask-note`. A reader meeting `ait obsolete ls`, a `review` prompt or an `OBSOLESCENCE:` line at pick time has nowhere to learn what a band means, why a dismissed task came back, or what "archive as obsolete" does.

This task writes that missing concept and workflow layer. Write it from what **shipped**, not from the design alone. The source of truth is `aidocs/framework/task_relations.md`, D9: "Evidence", "Judgement", "Surfaces and dispositions", and above all "Obsolescence API".

## Scope

1. **A concept page**, `website/content/docs/concepts/task-obsolescence.md` (or a section of t1981_8's relations concept page if that has landed first; coordinate rather than duplicate). It should explain:
   - what an assessment is: a band (`none` / `low` / `medium` / `high`), evidence-backed reasons and a disposition (`keep` / `refresh` / `fold_into` / `drop`). It is advisory and **never auto-actioned**;
   - **signal versus context evidence.** Signal rows are the only scoring inputs: an origin that was reverted, archived with a reason, folded or deleted; `superseded_by` / `duplicate_of` / `affected_by_landed` relations; a stale premise. Context rows are shown for inspection only: path facts, age, a non-stale premise, a completed origin. Explain in plain words why path facts never assert obsolescence;
   - "no signal row ⇒ band `none`, no agent run";
   - unreadable evidence: a corrupt or unreachable relations store is reported as unknown, never as a clear task;
   - dismissals: keyed to the evidence, so a dismissed task resurfaces only when its evidence changes;
   - that it shares the relations layer's opt-in: off by default, with the cost of an agent run, the per-host daily cap counted per operation, and `AIT_RELATIONS=0`.
2. **A workflow page**, `website/content/docs/workflows/obsolete-tasks.md` or similar. It should cover:
   - finding candidates: `ait obsolete ls [--min-band]`, `show`, `evidence`;
   - the `review` walk, which acts only on an explicit choice letter:
     - open;
     - fold, where both tasks are validated and a refusal changes nothing;
     - archive as obsolete, including the gate-pending second confirmation;
     - dismiss;
     - skip;
   - when assessments are made: the landed trigger after a successful archive commit of completed work, and `ait obsolete sweep [--budget N]` with its fair rotation;
   - the `OBSOLESCENCE:` band at pick time (`related-work --point pick`);
   - `ait obsolete unblock` for a stuck invocation.
3. **The archive behaviour**, as t2254 shipped it: archiving a parent's last child with `--obsolete` / `--superseded` gives the parent the reason only when none of its children landed. Link `development/task-format.md` (`archived_reason`) and `concepts/parent-child.md`; do not restate them.
4. **Cross-links**: from the premise-staleness workflow page (its verdict is one evidence row), from the related-work check docs, and from the `concepts/` and `workflows/` indexes.

## Out of scope

- The `ait relations` / `ait obsolete` CLI reference, the relations concept page and the TUI page: those belong to t1981_8. Link to its pages where they exist.
- Agent-tree ports: t1981_9.

## Rules

- Follow `aidocs/framework/documentation_conventions.md` (current state only; genericize agent names) and the doc guide `aitasks/metadata/doc_update_guide.md` (reader levels, concept-page rules).
- Prefer `{{< relref >}}` links. Run `python3 check_links.py --build` in `website/` after editing, and offer `check_link_relevance.py` for the new links.

## Verification

- `hugo build --gc --minify` succeeds, and `check_links.py --build` is clean.
- Every verb, flag, line prefix and band or disposition name in the pages exists in the shipped code: grep `.aitask-scripts/aitask_obsolete.sh`, `lib/obsolete_cli.py`, `lib/obsolescence_evidence.py` and `lib/relations_schema.py`.
- Nothing in the pages contradicts the "Obsolescence API" section of `aidocs/framework/task_relations.md`.
