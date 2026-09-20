---
Task: t1687_2_concepts_attachments_and_attach_command.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
---

# t1687_2 — Attachments concept page and `ait attach` reference

## Goal

Give attachments their first real documentation: a concept page
(`concepts/attachments.md`, weight 55, *Data model*) and a command reference
(`commands/attach.md`, weight 34, `depth: [intermediate]`), wired into
`commands/_index.md`.

Today the entire website coverage of `ait attach` is two rows in
`development/task-format.md` — this is almost all new prose, and the one page in
the sweep with no duplication risk.

## Pre-phase (risk mitigations)

### record_page_ownership_notes

The parent sent the ownership note to t1231_3 at decomposition. If it did not
land, send it before writing:

```bash
./ait note 1231_3 --from 1687_2 --file - <<'EOF'
t1687 planning (2026-09-20) decided t1687 LEAVES concepts/artifacts.md and
commands/artifact.md to you — your plan covers the gitbranch backend this task
cannot document. t1687_2 takes only the unowned attachments side
(concepts/attachments.md + commands/attach.md) and does NOT touch the bare
`ait artifact` literals at development/task-format.md:98-99 or
skills/aitask-trail.md:85, so your retarget decision stays open.
Advisory only — verify before acting.
EOF
```

## Implementation

### 1. Read the sources

- `aidocs/task_attachments_design.md` — the model.
- `aidocs/attachment_metadata_bucketing.md` — metadata layout.
- `.aitask-scripts/aitask_attach.sh` — the real verb surface and its refusals.
- `./ait attach --help` and `./ait attach` for the shipped verb list. The
  dispatcher's own help line reads
  "Manage task file attachments (ls; add/get/rm/move/gc pending)" — **check what
  is actually implemented before documenting a verb as available.** Do not
  document a pending verb as shipped; current-state-only prose applies.
- `website/content/docs/development/task-format.md:60` and `:78-101`.

### 2. Write `concepts/attachments.md`

```yaml
---
title: "Attachments"
linkTitle: "Attachments"
weight: 55
description: "..."
depth: [intermediate]
---
```

Angle: **content-addressing as the identity model.** Cover:

- an attachment is identified by `hash` (`sha256:…`), never by path or name —
  the name is a label, the hash is the identity;
- the nested `attachments:` frontmatter block (`hash`, `name`, `mime`, `size`,
  `added_at`, `backend`) and that it is never hand-edited;
- why `ait attach` commits the blob, the metadata and the task file as one unit,
  and therefore refuses to run while the task file has uncommitted changes;
- backends and where blobs live;
- refcounting and `gc`: the same blob referenced by two tasks is stored once, and
  removing one reference does not delete it.

Shape per `concepts/framework-session.md`: `## What it is` → `###` subsections →
`## Why it exists` → `## How to use` → `## See also` → `---` → `**Next:**`.

The "How to use" section should be short and defer to `commands/attach.md`.

### 3. Write `commands/attach.md`

Copy the frontmatter and section shape of `website/content/docs/commands/lock.md`
(weight in the 30s, `depth: [intermediate]`). Open with the `crew.md` pattern:

> `ait attach` manages a task's file attachments — content-addressed blobs stored
> beside the task rather than inside it. For the conceptual model (content
> addressing, backends, refcounting), see the
> [Attachments concept page]({{< relref "/docs/concepts/attachments" >}}).

Then one `##` per implemented verb, documenting flags, output and exit codes as
`lock.md` does. Document only verbs that actually work today.

### 4. Wire it into `commands/_index.md`

Two edits, both in the file's **relative** link style (measured 2 relref : 33
relative — match the table, do not introduce relref here):

- a row in the **Tools** category table:
  `| [`ait attach`](attach/) | Manage a task's content-addressed file attachments |`
- a line in the `## Usage Examples` fenced bash block, near the `ait note` lines.

### 5. Link the bare `ait attach` literal — and only that one

`development/task-format.md:98-99` reads (approximately):

> `artifacts` entries are written by `ait artifact` and `attachments` entries by
> `ait attach`; both commands manage the blob, the manifest and the task file as
> one commit …

Link **`ait attach`** to `{{< relref "/docs/commands/attach" >}}`.

**Leave `ait artifact` unlinked.** t1707 removed its dead-end relref
deliberately so that t1231_3 could choose the target; re-linking it here would
undo that decision. The same holds for `skills/aitask-trail.md:85` — do not
touch it.

Also add the concept relref to the `attachments` row at line 60 and to the
`### Nested fields: artifacts and attachments` section at line 78. Both are
relref (file is 10:1).

## Post-phase (risk mitigations)

### link_relevance_triage (shared with t1687_5)

Confirm the new `commands/attach.md` is reachable from `commands/_index.md`, and
re-grep to prove `ait artifact` is still unlinked in both protected locations:

```bash
grep -n 'ait artifact' website/content/docs/development/task-format.md \
                        website/content/docs/skills/aitask-trail.md
```

Neither hit should carry a relref or a relative link.

## Constraints

- Full path `/docs/concepts/attachments` in every relref.
- **No mermaid** on this site.
- Current-state-only prose; do not document pending verbs as shipped.
- Do **not** touch `concepts/_index.md` — t1687_5 owns it. The
  `commands/_index.md` row *is* this task's job.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Check `${PIPESTATUS[0]}` or `set -o pipefail`.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.
