---
Task: t2258_8_retrospective_doc_levels.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_8 — Retrospective: reader levels and readable prose

## Context

Closes t2258: measures the outcome, reconciles skipped pages, and decides the
items the parent deferred. Inputs: the archived plans of t2258_1 … t2258_7 (and
any `audit_deferred_pages_*` siblings) under `aiplans/archived/p2258/`.

## Steps

1. **Reader-test comparison.** From `p2258_3`'s "Reader reports — before/after",
   tabulate per page: guessed terms, unneeded details, ambiguities,
   contradictions (before → after), controls included. Run the fresh-reader test
   on 3–5 restructured `main-concept` pages from children 4–7 and add them.
   Conclude in a few sentences whether pages got clearer for the beginner persona.
2. **Skipped-page reconciliation.** List every ledger entry from children 3–7
   with its outcome. Entries with neither `audited` nor an open
   `audit_deferred_pages_*` child: audit the page now or create the follow-up
   child (`--parent 2258 --no-sibling-dep`). Put the list of outstanding
   follow-ups in Final Implementation Notes (the parent's completion report
   names them).
3. **Decisions**, each with reasons in Final Implementation Notes; create a task
   only where the data supports one:
   - project-agnostic `## Reader levels` for `seed/doc_update_guide.md`;
   - Vale + `tbhb/vale-ai-tells` as an advisory sensor (never a gate);
   - content-hash audit trail for the docs gate's drafts;
   - a t2186 eval follow-up once it supports judge-scored prompts.
4. **Port tasks** for `aitask-doc-review`: Codex (`.agents/skills/`) and OpenCode
   (`.opencode/skills/` + `.opencode/commands/`), via the Batch Task Creation
   Procedure (parent tasks, `--followup-of 2258`).

## Verification

- Comparison table, reconciliation list and four decisions are recorded.
- No ledger entry lacks an outcome.
- Port tasks exist (`./.aitask-scripts/aitask_ls.sh -v 50 | grep -i doc_review`).

## Post-implementation

Step 9 (review, commit `documentation: … (t2258_8)`, archival). With all
children archived, the parent t2258 archives.
