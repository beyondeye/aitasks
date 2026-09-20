---
priority: medium
effort: medium
depends: [t1687_2]
issue_type: documentation
status: Ready
labels: [documentation, website, concepts]
gates: [risk_evaluated]
anchor: 1687
created_at: 2026-09-20 12:01
updated_at: 2026-09-20 12:01
---

## Context

Part of t1687 (Concepts docs gap sweep). Two concept pages that share a theme:
context that crosses a boundary — between tasks, and between repositories.

**Re-verified 2026-09-20:** the task-notes row in t1687's original gap table
("zero website coverage, biggest single hole") is **stale**. Commit `0e5b965fa`
(t1657_6) added `workflows/task-notes.md`, `commands/note.md` and
`skills/aitask-note.md`. Only the *concept* page remains, and it must be written
as a complement, not a restatement — see the angle section below.

## Key files to modify

- **NEW** `website/content/docs/concepts/task-notes.md` — weight **45**,
  group *Data model*.
- **NEW** `website/content/docs/concepts/cross-repo-references.md` — weight
  **115**, group *Lifecycle and infrastructure*.

Back-links (all relref; every one of these files is relref-dominant or
relref-exclusive):

| Target | Insertion point |
|---|---|
| `website/content/docs/workflows/task-notes.md` | `## See also` (line 89) |
| `website/content/docs/commands/note.md` | `#provenance` (line 129) |
| `website/content/docs/skills/aitask-note.md` | `## Related` (line 58) |
| `website/content/docs/workflows/multi_project.md` | `#why-logical-project-names` (line 11) |
| `website/content/docs/workflows/cross_project_dependencies.md` | `## See also` (line 122) |
| `website/content/docs/development/task-format.md` | `xdeprepo` row (line 39), beside the existing relref |

## Do NOT link

- `website/content/docs/concepts/locks.md` — a single passing mention of
  `ait note`, not an explanation. It also does not qualify under the
  "explains the concept inline" rule, and t1592/t1593 are both editing it.
- Any `Inbox` hit under `tuis/board/*`, `commands/task-management.md` or
  `tuis/minimonitor/how-to.md` — those are the board's "Unsorted / **Inbox**"
  column, an unrelated homonym.
- `commands/_index.md` `### Cross-repo` — pure command reference, one row that
  already points at both workflow pages.

## Reference files for patterns

- `website/content/docs/concepts/framework-session.md` — concept page shape.
- `website/content/docs/commands/crew.md:9-12` — back-link sentence pattern.

## Content sources

`aidocs/framework/task_note_mailbox.md`,
`aidocs/framework/live_endpoint_resolution.md`,
`aidocs/framework/cross_repo_references.md`.

## Complementary angle (MANDATORY — both pages duplicate heavily otherwise)

**`concepts/task-notes.md` angle:** why cross-task context is **untrusted by
construction**, and what provenance can and cannot prove.

Must NOT restate:
- `workflows/task-notes.md:9` (what a note is), `:38-81` (the two delivery
  lanes, receiving, where notes surface).
- `commands/note.md:129-151` `### Provenance` — the only full definition of
  `from` / `from_verified` / `base` / `dirty` anywhere. Reference it; do not
  re-tabulate it.

Cover instead: why `from=` is a *claim* and an absent `from_verified` means
*not proven* rather than disproof; why a SHA dates tree-relative claims but not
moment-relative ones (`dirty`); why unread state is derived rather than stored;
and why displaying is separated from acknowledging.

**`concepts/cross-repo-references.md` angle:** why a **logical name resolved at
call time** is the identity, not a path.

Must NOT restate `workflows/multi_project.md:11-13` (why logical names),
`:34-51` (the registry file), `:145-158` (the `<project>#<id>` /
`<project>:<path>` notation). Cover the identity model and why `xdeps` without
`xdeprepo` is rejected.

## Constraints

- **Slug collision:** `/docs/concepts/task-notes` collides with
  `/docs/workflows/task-notes`. **Always use the full `/docs/...` path** — a
  bare `{{< relref "task-notes" >}}` is ambiguous and FAILS the build.
- **No mermaid** on this site (builds green, renders as a plain code block).
- Current-state-only prose per `aidocs/framework/documentation_conventions.md`.
- Do **not** add `concepts/_index.md` bullets here — t1687_5 owns that file.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Use `set -o pipefail` or check `${PIPESTATUS[0]}`. The build is the guard that
catches an ambiguous relref, so run it before committing.
