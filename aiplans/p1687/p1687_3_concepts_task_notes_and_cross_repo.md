---
Task: t1687_3_concepts_task_notes_and_cross_repo.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
---

# t1687_3 — Task notes and cross-repo references

## Goal

Two concept pages for context that crosses a boundary:

- `concepts/task-notes.md` — weight **45**, *Data model*
- `concepts/cross-repo-references.md` — weight **115**,
  *Lifecycle and infrastructure*

## The duplication problem (read before writing)

Both concepts are already explained inline, and well. The parent task's whole
warning is that Concepts must not become a duplicate index of the rest of the
site. The rule for this task: **state the model the existing pages assume, and
link to them for the mechanics.**

| Already owns | Do not restate |
|---|---|
| `workflows/task-notes.md:9` | what a note is |
| `workflows/task-notes.md:38-81` | the two delivery lanes, receiving, where notes surface |
| `commands/note.md:129-151` `### Provenance` | the only full `from` / `from_verified` / `base` / `dirty` table on the site |
| `workflows/multi_project.md:11-13` | why logical names |
| `workflows/multi_project.md:34-51` | the registry file |
| `workflows/multi_project.md:145-158` | the `<project>#<id>` / `<project>:<path>` notation |

## Implementation

### 1. `concepts/task-notes.md` (weight 45)

Angle: **why cross-task context is untrusted by construction, and what
provenance can and cannot prove.**

```yaml
---
title: "Task Notes"
linkTitle: "Task notes"
weight: 45
description: "..."
depth: [intermediate]
---
```

Cover, as a *model* rather than a field reference:

- **The inbox is part of the task file.** A note is appended to `## Inbox` and
  committed; that is what makes it durable and what makes it survive nobody
  working on the task.
- **`from=` is a claim, not an identity.** Only `from_verified: yes` upgrades it,
  and an empty value means *not proven* — never disproof. This asymmetry is the
  page's core idea.
- **A SHA dates tree-relative claims, not moment-relative ones.** `base` fixes
  what the tree looked like; `dirty` warns that a reading like `git status` may
  already be stale in a way no SHA catches. An empty `dirty` is "not measured",
  never "clean".
- **Unread state is derived, not stored** — which is why displaying a note and
  acknowledging it are deliberately separate operations.
- **A note never instructs.** It is advisory input; consuming it is the reader's
  decision, and it never bypasses planning, gates or review.

Link `commands/note.md#provenance` for the field table rather than repeating it.

### 2. `concepts/cross-repo-references.md` (weight 115)

Angle: **why a logical name resolved at call time is the identity, not a path.**

Cover: the per-user registry at `~/.config/aitasks/projects.yaml`; why a
hardcoded `../backend/` breaks across machines, cloud agents and re-clones; the
`<project>#<id>` task notation and `<project>:<path>` file notation; and why
`xdeps` without `xdeprepo` is rejected (task IDs are meaningless without a
project to resolve them against) while `xdeprepo` alone is legal and declares
intent to coordinate.

Source: `aidocs/framework/cross_repo_references.md`.

### 3. Back-links (all relref — every target is relref-dominant or -exclusive)

| File | Insertion point | Measured form |
|---|---|---|
| `workflows/task-notes.md` | `## See also` (line 89) | 12:0 relref |
| `commands/note.md` | `#provenance` (line 129) | 5:0 relref |
| `skills/aitask-note.md` | `## Related` (line 58) | 8:1 relref |
| `workflows/multi_project.md` | `#why-logical-project-names` (line 11) | its only link is a relref |
| `workflows/cross_project_dependencies.md` | `## See also` (line 122) | 7:0 relref |
| `development/task-format.md` | `xdeprepo` row (line 39) | 10:1 relref |

### 4. Do not link

- `concepts/locks.md` — one passing mention of `ait note`, not an explanation,
  and t1592/t1593 are both editing that file.
- Any `Inbox` hit under `tuis/board/*`, `commands/task-management.md` or
  `tuis/minimonitor/how-to.md` — that is the board's "Unsorted / **Inbox**"
  column, an unrelated homonym.
- `commands/_index.md` `### Cross-repo` — a single command row that already
  points at both workflow pages.

## Post-phase (risk mitigations)

### link_relevance_triage (shared with t1687_5)

These two pages are the most likely in the sweep to read as restatements.
Re-read each against its Workflows counterpart and cut anything that merely
repeats it.

## Constraints

- **Slug collision:** `/docs/concepts/task-notes` collides with
  `/docs/workflows/task-notes`. **Always write the full `/docs/...` path.** A
  bare `{{< relref "task-notes" >}}` is ambiguous and fails the build — run
  `hugo build` before committing, since that is the check which catches it.
- **No mermaid** on this site.
- Current-state-only prose.
- Do **not** touch `concepts/_index.md` — t1687_5 owns it.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Check `${PIPESTATUS[0]}` or `set -o pipefail`.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.
