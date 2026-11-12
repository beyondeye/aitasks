---
priority: medium
effort: medium
depends: [t2258_7]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:10
updated_at: 2026-11-09 23:10
---

## Context

Child 8 of t2258 — the retrospective. It closes out the parent's goal and
decides the open items the parent deliberately deferred. Read the parent task
`aitasks/t2258_doc_audience_levels_and_readable_prose.md`, the approved parent
plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`, and the
archived plans of siblings `t2258_1` … `t2258_7` (and any
`audit_deferred_pages_*` siblings), under `aiplans/archived/p2258/`.

## Work

1. **Reader-test comparison.** Compare the before/after fresh-reader reports
   recorded by `t2258_3` (six long concept pages + the `tasks.md` / `plans.md`
   controls): guessed terms, unneeded details, ambiguities, per page. Run the
   fresh-reader test on a sample of 3–5 restructured pages from children 4–7.
   Summarise whether the level model and review made pages measurably clearer
   for the beginner persona.
2. **Skipped-page reconciliation.** Collect every skipped-page ledger entry
   from children 3–7 (their Final Implementation Notes). Each must have an
   outcome: `audited`, or an open `audit_deferred_pages_*` child of t2258.
   Any entry with neither is a defect — audit the page here or create the
   follow-up child. List all outstanding follow-ups in this child's notes so
   the parent's completion report names them.
3. **Decisions** (record each with reasons; create a task only when the data
   justifies it):
   - **Seed guide:** should `seed/doc_update_guide.md` (generic guide installed
     into other projects) gain a project-agnostic `## Reader levels` model, so
     `aitask-doc-review` runs its level check and fresh-reader test there too?
     (Without it, other projects get `not-run(no-level-model)`.)
   - **Vale + `tbhb/vale-ai-tells`** (MIT; ~137 rules, all at `error`, need
     per-rule tuning; Vale not installed here) as an optional *advisory* prose
     sensor — never a hard gate.
   - **Content-hash audit trail** for the docs gate's drafts (reviewed vs
     applied digests), deferred from `t2258_2`.
   - **t2186** (agent-prompt eval harness): once it supports judge-scored
     prompts, a follow-up that measures the review procedure across agents,
     including agents without sub-agents.
4. **Port tasks.** Create tasks to port `aitask-doc-review` to Codex
   (`.agents/skills/`) and OpenCode (`.opencode/skills/` + `.opencode/commands/`),
   per CLAUDE.md "Working on Skills".

## Verification

- The comparison table, the reconciliation list and the four decisions are in
  the plan's Final Implementation Notes.
- No ledger entry from children 3–7 lacks an outcome.
- The port tasks exist (`./.aitask-scripts/aitask_ls.sh -v 50 | grep doc_review`).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258_2** id=2026-11-10T14:18:18Z.734a96278482c49074662ba9 from=t2258_2 from_verified=yes at=2026-11-10T14:18:18Z base=2f816eabe5d2bf807b62aac35edbeaa31f55f9b8 base_branch=main dirty=yes host=omg16
>
> | The review skill that t2258_2 built is named `aitask-docs-review` (renamed at review, to match `aitask-docs-gap`), not `aitask-doc-review` as this task's body and plan say.
> | - Skill: .claude/skills/aitask-docs-review/SKILL.md
> | - Invocation: /aitask-docs-review <page>... [--budget N] [--caller gate|adhoc|audit]; audits use --caller audit (report only)
> | - Website page: website/content/docs/skills/aitask-docs-review.md
> | - Contract test: tests/test_docs_review_contract.sh
> | Read every `aitask-doc-review` reference in this task as `aitask-docs-review`.

> **✉ note:t2258_3** id=2026-11-12T06:51:18Z.0f3a67a365e538016444508e from=t2258_3 from_verified=yes at=2026-11-12T06:51:18Z base=7f1f4333a3379c4641e0a4b85281072e25ea2240 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_3 (concepts pilot), for the retrospective. Before/after reader reports, verbatim, and the counts are in aiplans/archived/p2258/p2258_3_*.md.
> | Caveats when comparing:
> | (1) The pilot's reader questions were written by the orchestrator after it had read the pages. Before and after use the same questions, but the absolute "unneeded" counts may be low. The skill now has the reader sub-agent write its own questions before it sees the page.
> | (2) Gates ran three times on near-identical text and scored 27, 33 and 28: expect a few points of run-to-run variance.
> | (3) The controls tasks/plans were edited in Step 4, so in the after run only the scratch Labels page is an unedited floor.
> | (4) The first separation test failed (questions mirrored sections; navigation was counted as unneeded). That led to the Step 4 tuning.
> | The guide grew by about 48/-14 lines (boundary plus pilot lessons).
