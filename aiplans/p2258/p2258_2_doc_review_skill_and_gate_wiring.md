---
Task: t2258_2_doc_review_skill_and_gate_wiring.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_2 — `aitask-doc-review` skill and `docs_updated` gate wiring

## Context

The procedure half of t2258. Binding text: parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md` — Design decisions 2,
3, 5, 6; Pre-phase `gate_review_cost_bound`; Post-phase
`doc_review_gate_contract_test`; the child-2 Verification bullets. Those went
through three review rounds (reviewed-draft input, cumulative budget,
five-state destination check incl. concurrent create/delete, merge-file error
handling). Implement them as written.

### Pre-phase (risk mitigations)

1. [gate_review_cost_bound] The review procedure keeps one gate run bounded:
   level/prose check is one in-context pass per page; fresh-reader runs (sub-agent
   or self-review) only for edited beginner-level pages, **budget 3 per gate run,
   cumulative across every review and re-review**; the gate passes the remaining
   budget in and the skill returns the amount used; within a pass pick by most
   changed body lines; leftovers `reader=not-run(cap)`, listed at confirm; extra
   tests only on the user's explicit "Run more fresh-reader tests" choice, never
   in autonomous profiles; no budget used in the no-level-model case.

## Steps

1. **Read** `aidocs/framework/skill_authoring_conventions.md`, the current gate
   skill, `aitask-docs-gap` Step 6, `tests/test_gate_procedure_docs.sh`,
   `tests/lib/asserts.sh`, and child 1's new guide sections.
2. **Write `.claude/skills/aitask-doc-review/SKILL.md`:**
   - frontmatter (`name`, `description`); purpose; invocation (page drafts or
     live paths; remaining budget; caller = gate | ad-hoc | audit);
   - guide resolution via `aitask_resolve_config_path.sh doc_update.guide
     aitasks/metadata/doc_update_guide.md`; interface detection
     (`## Reader levels` + level field + beginner value + personas);
   - procedure invariants (prose only; no invented facts; moved-not-deleted);
   - level/prose check (per page, in-context), output format;
   - fresh-reader test (questions, sub-agent with page text inline and the
     persona, follow-up questions, report lists; self-review fallback);
   - `reader=` values (six, exact strings); budget rules (pre-phase above);
   - no-level-model path.
   No rule text from the guide is copied in.
3. **Edit the gate skill** `.claude/skills/aitask-gate-docs-updated/SKILL.md`:
   step 3 drafts (`.draft` + `.base` under
   `.aitask-gates/<task-id>/docs_updated_<run-id>_drafts/`); new step 3b review;
   step 4 report + budget + "Run more fresh-reader tests" + Adjust → re-review;
   step 5 five-state table, `git merge-file` only in "modified", rc 0 / 1–127 /
   other handling, created/deleted → back to step 3, reconciled drafts
   re-reviewed and re-confirmed; step 6 log fields. Update its MUST NOT list
   (never apply over a non-unchanged destination; never treat a merge error as
   reconciliation).
4. **Wrappers.** Check whether the Codex/OpenCode gate wrappers embed text that
   changed; refresh via `aitask_audit_wrappers.sh apply-wrapper … --force` only
   if so.
5. **`aitask-docs-gap` Step 6**: add the `**Target level:**` line to the gap
   template and one sentence on choosing it from the guide's level model.
6. **Website page** `website/content/docs/skills/aitask-doc-review.md` (depth
   `intermediate`; what it is for, when the gate runs it, ad-hoc use, what the
   report means); update the skills `_index.md` if it lists pages by hand; run
   `cd website && python3 check_links.py --build`.
7. **Dry runs** in a scratch copy (scratchpad): reviewed-draft run; four
   destination-change runs (modified-clean, modified-conflicting, created,
   deleted); no-level-model run (scratch config → copy of
   `seed/doc_update_guide.md`). Record summaries in Final Implementation Notes.

### Post-phase (risk mitigations)

1. [doc_review_gate_contract_test] `tests/test_doc_review_contract.sh`,
   self-contained, asserting: gate review step between 3 and 4; drafts + base
   files; Adjust/reconciliation re-review; five destination states, merge-file
   only in "modified", rc outside 0–127 = error applying nothing, created/deleted
   back to proposal; skill resolves guide via the resolver and names
   `## Reader levels` as its only interface heading; no bullet line from the
   guide's prose-rules section appears in the skill; all six `reader=` values in
   step 6; budget 3 per run cumulative, most-changed-first, explicit
   authorization; no-level-model skips level check and fresh-reader. Pre-fix
   control: the same assertions against `git show HEAD:<gate path>` (pre-change)
   must fail.

## Verification

- `bash tests/test_doc_review_contract.sh` passes; pre-fix control fails.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `check_links.py --build` exits 0.
- Dry-run summaries recorded.

## Post-implementation

Step 9 (review, commit `enhancement: … (t2258_2)`, archival). Suggest
Codex/OpenCode port tasks for `aitask-doc-review` (child 8 creates them).
