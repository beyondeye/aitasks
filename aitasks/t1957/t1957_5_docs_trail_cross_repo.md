---
priority: medium
effort: low
depends: [1957_1, 1957_4]
issue_type: documentation
status: Ready
labels: [trails, cross_repo, documentation]
gates: [risk_evaluated]
anchor: 1957
created_at: 2026-10-12 21:32
updated_at: 2026-10-12 21:32
---

## Context

Part of t1957 (parent plan:
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`). Documents the
user-facing behaviour delivered by t1957_1 (cross-repo blocker indicator on
trail cards, live status of cross-repo ghost members), t1957_2
(`ait trails --trail <handle>`), and t1957_4 (`L` Linked Trails action and
cross-session jump, incl. session bootstrap and the incomplete-scan rows).
Read the archived plans of those siblings (`aiplans/archived/p1957/`) for the
exact strings, keys and messages that shipped.

## Key Files to Modify

- `website/content/docs/workflows/cross_project_dependencies.md` — trail
  indicator (`↗`, `🌐 blocked (cross-repo)`, `(checking…)`), ghost live status,
  the linked-trail definition (four directions), the jump and what happens when
  the target session is not running or the target repo is on an older
  framework.
- `website/content/docs/tuis/trails/` pages — the new `L` key, `--trail`
  launch flag, card lines; keybinding table.
- Board By-Trail docs (`website/content/docs/tuis/board/`) where trail keys are
  listed — `L` applies there too.

## Reference

- `aidocs/framework/documentation_conventions.md` — current-state-only prose,
  no version history.
- CLAUDE.md website section: prefer `{{< relref >}}` for internal links.

## Implementation Plan

1. Read the shipped sibling plans/code for exact UI strings.
2. Update the three doc areas above.
3. `cd website && python3 check_links.py --build`; offer
   `python3 check_link_relevance.py` if links were added or retargeted.

## Verification

- `check_links.py --build` passes; `hugo build --gc --minify` succeeds.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1957_1** id=2026-10-13T05:40:11Z.67c97887108f3a9dd10b0607 from=t1957_1 from_verified=yes at=2026-10-13T05:40:11Z base=3f00a25852b2683a4efd05c490efdb98eaf767c5 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1957_1 (implemented and committed in 3f00a2585). Your task body lists the trail-card indicator as `↗`, `🌐 blocked (cross-repo)` and `(checking…)`. What actually shipped, as of that commit:
> | 
> | - A trail member's xdep refs each show one of three states inside the `↗ ...` line:
> |   - checked: `repo#id` (Done), `repo#id [Status]`, or `repo#id (UNREACHABLE)` (unreachable project or missing task);
> |   - `repo#id (checking…)`: a status check is running for it;
> |   - `repo#id (not checked)`: nobody has checked it yet. Typical cause: an xdep added on disk and then `r` (local refresh, which never starts a subprocess). `d` (reload) or a board sync checks it.
> | - `🌐 blocked (cross-repo)` appears only when a FINISHED check says a ref is not Done. Refs that are being checked or not checked never mark a member blocked.
> | - Cross-repo members (`proj#id` ghost cards) gain a live status line: `📋 <Status>`, `🌐 (UNREACHABLE)`, `🌐 (checking…)` or `🌐 (not checked)`. The ghost is struck through (landed) only when its own repo reports Done.
> | - Checks run in the background with the drift check: when a trail is opened, on `d`, on board sync and when the view is entered. Tab switches and `r` reuse the cached results.
> | 
> | Reference: the "Final Implementation Notes" in the archived p1957_1 plan. Take this as context, not a requirement; your own docs plan decides what to describe.

> **👁 note:read** id=2026-10-14T15:43:55Z.6e611336fba8f4ed2b536ef2 by=t1957_5 at=2026-10-14T15:43:55Z mode=explicit ids=2026-10-13T05:40:11Z.67c97887108f3a9dd10b0607
