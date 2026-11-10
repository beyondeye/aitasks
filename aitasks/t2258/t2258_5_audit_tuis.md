---
priority: medium
effort: medium
depends: [t2258_4]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
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
