---
priority: medium
effort: medium
depends: [t2258_13]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-12 11:39
---

## Context

Child 5 of t2258: audit `website/content/docs/tuis/` (32 pages). Each TUI already has `_index` / `how-to` / `reference` pages (the Diátaxis split), but mechanism leaks into how-tos — e.g. `tuis/minimonitor/how-to.md` explains the refresh cycle, `exit()` and a 5-second startup grace period to end users; move such mechanism to the TUI's reference page or `aidocs/`. Document only: board, monitor, minimonitor, codebrowser, settings, brainstorm (plus applink, syncer, etc. pages that exist); never add `diffviewer`. `tuis/applink/reference.md` and `tuis/monitor/reference.md` were dirty from another session at planning time, and `tuis/applink/{how-to,reference}.md` lack `depth:` — apply the shared-file gate.

## Method (binding; full text in the parent plan's "Common audit method")

Read the parent task `aitasks/t2258_doc_audience_levels_and_readable_prose.md`,
the approved parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`,
and the archived plan of `t2258_3` (concepts pilot) for lessons learned. Rules:
the "Reader levels", "Page types", "How a subject spans levels" and "Prose
rules" sections of `aitasks/metadata/doc_update_guide.md`. Review procedure:
`.claude/skills/aitask-doc-review/SKILL.md`.

1. Inventory every page of the section in the plan: lines, `depth`, page type,
   verdict, violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the
   guide's level contract; the prose rules).
2. Shared-file gate before each edit: diff the page against HEAD; a page dirty
   from another session is not edited — record it in a **skipped-page ledger**
   (path, reason, dirty state seen). Before closing, re-check each entry: now
   clean → audit it here; still dirty → create a child of t2258 with
   `--no-sibling-dep` named `audit_deferred_pages_<section>` listing pages,
   violations and reason. Final Implementation Notes record each entry's
   outcome (`audited` / `follow-up t2258_<n>`); do not archive otherwise.
3. Restructure: mechanism moves to the page that owns it (reference page,
   workflow page, or `aidocs/` for contributor-only internals); split mixed
   pages; keep a short overview that links out. Record every moved fact
   (source → destination#anchor) in the plan.
4. `aitask-doc-review` on each edited page (fresh-reader on `main-concept`
   pages, within the budget).
5. `cd website && python3 check_links.py --build` (mandatory) and
   `python3 check_link_relevance.py` for retargeted links, opening every
   reported target.
6. Rule refinements go back into the guide's examples, not ad-hoc page fixes.
7. Add `depth:` to every untagged leaf page in the section.

## Verification

- Inventory table, moved-fact table and skipped-page ledger outcomes are in the
  plan.
- `check_links.py --build` exits 0.
- Every leaf page in the section has `depth:`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258_1** id=2026-11-10T11:32:47Z.123367c54d05c64bc812cf78 from=t2258_1 from_verified=yes at=2026-11-10T11:32:47Z base=b93a5f2582ceaeff7401415a25a8936cc7b29e90 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2258_1. Tree-relative claims; verify against the code before acting.
> | 
> | website/content/docs/tuis/minimonitor/how-to.md:23 (the "Auto-despawn" note) describes auto-close wrongly. It says the first refresh after the agent pane has gone triggers exit(). In .aitask-scripts/monitor/minimonitor_app.py (AUTO_CLOSE_CONFIRMATIONS = 2, _check_auto_close, and the 5.0 s mount-time check in the refresh tick):
> | - it closes only after two refreshes in a row each verifiably find only its own pane in its window;
> | - a failed tmux observation, an incomplete listing, a listing without its own pane, or another pane remaining resets the count;
> | - repeated failures never close it;
> | - no check runs in the first 5 seconds after mount.
> | No time bound holds, so do not write "within one refresh".
> | 
> | The new guide (aitasks/metadata/doc_update_guide.md, "Reader levels" example) uses this paragraph as its intermediate example. When you move the mechanism out of the how-to: put the user-observable conditions above on tuis/minimonitor/reference.md (no deadline), and the code-level detail (tmux query, counter, exit() call) in aidocs/. Neither destination states it today.

> **✉ note:t2258_2** id=2026-11-10T14:18:11Z.1e47804d828a9b32f6739df1 from=t2258_2 from_verified=yes at=2026-11-10T14:18:11Z base=2f816eabe5d2bf807b62aac35edbeaa31f55f9b8 base_branch=main dirty=yes host=omg16
>
> | The review skill that t2258_2 built is named `aitask-docs-review` (renamed at review, to match `aitask-docs-gap`), not `aitask-doc-review` as this task's body and plan say.
> | - Skill: .claude/skills/aitask-docs-review/SKILL.md
> | - Invocation: /aitask-docs-review <page>... [--budget N] [--caller gate|adhoc|audit]; audits use --caller audit (report only)
> | - Website page: website/content/docs/skills/aitask-docs-review.md
> | - Contract test: tests/test_docs_review_contract.sh
> | Read every `aitask-doc-review` reference in this task as `aitask-docs-review`.

> **✉ note:t2258_3** id=2026-11-12T06:51:12Z.ad293ccac908ec0bf306a220 from=t2258_3 from_verified=yes at=2026-11-12T06:51:12Z base=7f1f4333a3379c4641e0a4b85281072e25ea2240 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_3 (concepts pilot), committed in 7f1f4333a. Two TUI reference pages were edited when concept-page detail moved:
> | - tuis/board/reference.md received the By-Topic view description from concepts/topic-anchoring. "Has children" is now described as `ait ls` output only.
> | - tuis/frozenagent/reference.md: edits followed the framework-session restructure.
> | The rule check tests/test_board_reference_doc_literals passed after the edits. Moved-fact rows are in aiplans/archived/p2258/p2258_3_*.md.

> **✉ note:t2258_4** id=2026-11-12T09:39:55Z.f427aacf9813d4ecafdea537 from=t2258_4 from_verified=yes at=2026-11-12T09:39:55Z base=36f4dbf21144b1c2d26047659cacd842ddce00f5 base_branch=main dirty=yes host=omg16
>
> | Your dependency changed from t2258_4 to t2258_13. The workflows audit was split into t2258_4 and t2258_9–13, run sequentially, and you now start after the last of them. This keeps the original order: workflow restructures move behaviour detail onto TUI reference pages before you audit those pages. Expect workflow-sourced facts on TUI pages such as `tuis/board/reference.md`, the codebrowser reference, `tuis/sitrep/` and `tuis/trails/`. Each split child's archived plan holds the moved-fact table that says where each fact came from.

> **✉ note:t2258_4** id=2026-11-12T13:41:12Z.652b8ff4bb8146d5ab722d7d from=t2258_4 from_verified=yes at=2026-11-12T13:41:12Z base=86d4f4aba660abfb560be589d704b42b20b9a61f base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_4 (Tasks workflows audit), committed in 86d4f4aba.
> | 
> | Facts moved onto your pages:
> | - tuis/board/reference.md § "Opening file references": the 0/1/2+ Enter behaviour, the session lookup (own session, else the running `tmux.default_session`), the no-session warning, `Codebrowser launch failed: <err>`, and "last request wins". Also a new File Reference Picker row.
> | - tuis/codebrowser/reference.md § "Creating a task from the viewer" and § "Opening a file at a line range": the selection → `--file-ref` table, and the multi-range span from the lowest start to the highest end.
> | 
> | Fact-only fixes (not audited) on tuis/codebrowser/how-to.md, tuis/codebrowser/_index.md and tuis/board/how-to.md:
> | - without a selection of two or more lines, the reference is the whole file;
> | - the buttons are "Run in terminal" (Direct tab) / "Run in tmux" (Tmux tab);
> | - the board needs the project's tmux session to be running.
> | 
> | There is no chatlink TUI page. Its keys (r, w, q, j, ?) and the check panel are on the new commands/chatlink.md § "Status TUI". tuis/_index.md:29 still omits the check panel and the w wizard.
> | 
> | The moved-fact table is in aiplans/archived/p2258/p2258_4_*.md.
