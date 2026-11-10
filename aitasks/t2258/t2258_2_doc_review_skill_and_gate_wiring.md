---
priority: medium
effort: high
depends: [t2258_1]
issue_type: enhancement
status: Implementing
labels: [documentation, doc_quality, aitask_gate_docs_updated, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-10 13:38
---

## Context

Child 2 of t2258. Read the parent task
`aitasks/t2258_doc_audience_levels_and_readable_prose.md` and the approved
parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md` —
**Design decisions 2, 3, 5 and 6, the Pre-phase step `gate_review_cost_bound`,
the Post-phase step `doc_review_gate_contract_test` and the child-2 Verification
bullets are binding on this child** (they went through three rounds of review;
do not weaken them). Child 1 (`t2258_1`) wrote the rules into
`aitasks/metadata/doc_update_guide.md`; this child writes the **procedure**
that applies them, and wires it into the `docs_updated` gate and
`aitask-docs-gap`.

## Deliverables

1. **New skill `.claude/skills/aitask-doc-review/SKILL.md`** (user-invocable;
   plain SKILL.md, not a `.md.j2` profile-aware skill unless planning shows a
   reason). Input: a list of page drafts (paths to `.draft` files, or live page
   paths for ad-hoc use), the remaining fresh-reader budget. Output per page:
   level findings, prose findings, `reader=` value, reader report (terms it had
   to guess, details it did not need, ambiguities, contradictions), unresolved
   problems; plus budget used.
   - Resolves the guide with
     `./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md`
     and reads it. **Duplicates no rule text.** It owns only procedure
     invariants: rewrite prose only (never code blocks, inline code, commands,
     paths, URLs, frontmatter, link targets); add no facts, names or numbers;
     a fact cut from a page is moved to its owning page, never deleted.
   - Level model present ⇔ guide has `## Reader levels` with the level field,
     the beginner value and per-level personas. Absent → prose check against
     the guide's writing conventions only; level check and fresh-reader both
     `not-run(no-level-model)`; say so in the report.
   - Level/prose check: one in-context pass per page, no sub-agent.
   - Fresh-reader test (anthropics doc-coauthoring method, our procedure): only
     for pages at the declared beginner level; predict 5–10 questions a reader
     at that level would ask; give a sub-agent **only the page text inline**
     (tell it not to open files) plus the persona sentence and the questions;
     collect answers, then ask what was ambiguous, what it assumed, every term
     it had to guess, every detail it did not need. Agents without sub-agents:
     self-review checklist, `reader=self-review`.
   - `reader=` values: `subagent`, `self-review`, `not-run(not-beginner)`,
     `not-run(untagged)` (also a level finding — `depth` is required),
     `not-run(cap)`, `not-run(no-level-model)`.
   - Budget (pre-phase `gate_review_cost_bound`): caller passes remaining
     budget; within a pass choose beginner pages by most changed body lines;
     leftovers `not-run(cap)`.
2. **`docs_updated` gate** (`.claude/skills/aitask-gate-docs-updated/SKILL.md`):
   - Step 3 writes complete drafts: `.aitask-gates/<task-id>/docs_updated_<run-id>_drafts/<page path>.draft`
     and `<page path>.base` (copy of the page when drafting began; none for a
     new page). `.aitask-gates/` is gitignored.
   - New step 3b: run `aitask-doc-review` on the drafts (by file path, so every
     agent tree can follow it), with the run's budget of **3 fresh-reader tests,
     cumulative across every review and re-review**.
   - Step 4 shows the reader report, unresolved problems, pages left
     `not-run(cap)` and the remaining budget; adds a "Run more fresh-reader
     tests" option (explicit authorization; never in autonomous profiles).
     "Adjust" changes drafts and re-reviews the changed pages before asking
     again.
   - Step 5 applies per the five-state destination table in parent-plan
     decision 5 (unchanged existing / unchanged new → copy; modified → `git
     merge-file -p <current> <.base> <.draft>` with rc 0 clean, 1–127 conflicts
     resolved by hand with no markers left, any other rc = error that applies
     nothing; created or deleted by another session → back to step 3, never
     call merge-file). Reconciled drafts are re-reviewed and re-confirmed.
   - Step 6 log: per page `level=`, `prose=`, `reader=`, unresolved count;
     excluded/cap pages listed.
   - Codex / OpenCode surfaces are generated pointers — refresh with
     `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> aitask-gate-docs-updated --force`
     only if the wrapper text needs to change; otherwise leave them.
3. **`aitask-docs-gap`** (`.claude/skills/aitask-docs-gap/SKILL.md` Step 6): each
   `## Gap:` section gains `- **Target level:** <depth> · <page type>`.
4. **Website skill page** `website/content/docs/skills/aitask-doc-review.md`
   (with `depth:`), and the skills index if it lists skills by hand; run
   `cd website && python3 check_links.py --build`.
5. **Contract test** `tests/test_doc_review_contract.sh` per the parent plan's
   Post-phase step (assertions list there), with a pre-fix control.

## Reference files

- `.claude/skills/aitask-gate-docs-updated/SKILL.md` (current 6-step flow).
- `tests/test_gate_procedure_docs.sh` (existing gate-doc test pattern),
  `tests/lib/asserts.sh` (if test bodies run in subshells, opt into
  `assert_counters_init` / `assert_counters_load` — CLAUDE.md, t1207).
- `aidocs/framework/skill_authoring_conventions.md` before creating the skill.

## Verification

- `bash tests/test_doc_review_contract.sh` passes; its pre-fix control (run
  against the pre-change gate text, e.g. from `git show HEAD:<path>` into a
  scratch file) fails.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- The recorded dry runs in a scratch copy of the docs tree, listed in the
  parent plan's Verification (reviewed-draft run; four destination-change runs:
  modified-clean, modified-conflicting, created, deleted; no-level-model run
  with a scratch config pointing `doc_update.guide` at a copy of
  `seed/doc_update_guide.md`). Record each run's transcript summary in the
  plan's Final Implementation Notes.
- After this lands, suggest port tasks for Codex/OpenCode wrappers of
  `aitask-doc-review` (child 8 creates them).
