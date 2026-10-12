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
