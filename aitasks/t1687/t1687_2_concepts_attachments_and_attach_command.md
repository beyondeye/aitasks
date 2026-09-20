---
priority: medium
effort: medium
depends: [t1687_1]
issue_type: documentation
status: Ready
labels: [documentation, website, concepts]
gates: [risk_evaluated]
anchor: 1687
created_at: 2026-09-20 12:01
updated_at: 2026-09-20 12:01
---

## Context

Part of t1687 (Concepts docs gap sweep). Attachments are the worst-documented
shipped surface on the site: `ait attach` (ls / add / get / rm / move / gc)
exists as a real subcommand, `.aitask-scripts/aitask_attach.sh` is ~636 lines,
and the **only** website coverage is two rows in
`website/content/docs/development/task-format.md` plus one blog post. There is
no `commands/attach.md` and no concept page.

**Ownership decision made at t1687 planning (2026-09-20):** t1231_3 owns
`concepts/artifacts.md` and `commands/artifact.md` and is blocked on t1231_2
(the `gitbranch` backend its page must document). The user decided t1687
**leaves both artifact pages to t1231_3** and takes the unowned attachments
side. `ait attach` has no owner anywhere. A note recording this was sent to
t1231_3 before this task was created.

## Key files to modify

- **NEW** `website/content/docs/concepts/attachments.md` — weight **55**,
  group *Data model*.
- **NEW** `website/content/docs/commands/attach.md` — weight **34**,
  `depth: [intermediate]`, shaped on `website/content/docs/commands/lock.md`.
  Document `ls` / `add` / `get` / `rm` / `move` / `gc`.
- `website/content/docs/development/task-format.md` — the `attachments` row
  (line 60) and `#nested-fields-artifacts-and-attachments` (line 78), relref.
  **Also link the bare `ait attach` literal at lines 98-99** to the new command
  page.
- `website/content/docs/commands/_index.md` — add a row to the **Tools** table
  and a line to the `## Usage Examples` fenced block.

## CRITICAL constraint — leave `ait artifact` alone

`development/task-format.md:98-99` carries two adjacent bare literals:
`ait artifact` and `ait attach`. t1707 deliberately removed the dead-end relrefs
from both so the retarget decision would not be guessed. **Link only
`ait attach`. Leave `ait artifact` unlinked** — that is t1231_3's decision.
The same applies to the bare `ait artifact` literal at
`website/content/docs/skills/aitask-trail.md:85`: do not touch it.

## Link form (measured; per-FILE, not per-directory)

| File | relref : relative | Use |
|---|---|---|
| `development/task-format.md` | 10 : 1 | relref |
| `commands/attach.md` (new) | n/a | relref |
| `commands/_index.md` tables | 2 : 33 | **relative** — `[...](../concepts/attachments/)` |

The `commands/_index.md` category tables and usage block are uniformly
relative; a new row must match its table, not the site-wide preference.

## Reference files for patterns

- `website/content/docs/concepts/framework-session.md` — concept page shape.
- `website/content/docs/commands/lock.md` — command page shape and frontmatter.
- `website/content/docs/commands/crew.md:9-12` — the back-link sentence pattern.

## Content sources

`aidocs/task_attachments_design.md`, `aidocs/attachment_metadata_bucketing.md`,
`.aitask-scripts/aitask_attach.sh`.

## Complementary angle (MANDATORY)

The concept page's angle: **content-addressing as the identity model — why a
blob is named by its hash and never by a path.** Cover backends, refcounting and
gc, and the nested `attachments:` frontmatter block.

This is the one page with almost no duplication risk — only two rows exist
today, so it is nearly all new prose. Keep the CLI surface on `commands/attach.md`
and the model on the concept page.

## Constraints

- **No mermaid** on this site — a mermaid fence builds green but renders as a
  plain code block. Use box-drawing ASCII in a ```text fence if a diagram helps.
- Current-state-only prose per `aidocs/framework/documentation_conventions.md`.
- Do **not** add the `concepts/_index.md` bullet here — t1687_5 owns that file.
  (The `commands/_index.md` row IS this task's job.)

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Use `set -o pipefail` or check `${PIPESTATUS[0]}`. Confirm the new
`commands/attach.md` is reachable from `commands/_index.md`, and that
`ait artifact` is still unlinked in both places named above.
