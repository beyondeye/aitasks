---
Task: t565_document_the_aitask_from_file_workflow.md
Base branch: main
plan_verified: []
---

# Plan — t565: Document the file-references / create-from-codebrowser workflow

## Context

`v0.16.0` shipped a cohesive new workflow for creating aitasks from specific files
and line ranges in `ait codebrowser`, with auto-merge of overlapping pending
tasks through the `ait create` script. The task description references "task
461", but verification against `CHANGELOG.md:7-8` and the archived plans shows
the actual feature landed as **t540_1 through t540_8** (t461 is a separate
feature on launch modes). Nothing about the new workflow is currently
documented on the website — the only mention is a single paragraph in the
v0.16.0 release blog post. This plan closes that documentation gap.

Concretely, the feature surfaces in four places that all need mention in the
website docs:

1. **Frontmatter** — a new `file_references: [path, path:N, path:N-M^N-M, ...]`
   field on task files.
2. **Create script** — new `--file-ref`, `--auto-merge`, `--no-auto-merge`
   CLI flags on `aitask_create.sh`; `aitask_update.sh` gains `--file-ref` /
   `--remove-file-ref`; a new helper `aitask_find_by_file.sh` drives auto-merge
   detection; `aitask_fold_*` scripts union `file_references` on fold.
3. **Codebrowser** — new `n` keybinding spawns interactive
   `aitask_create.sh --file-ref <path>[:start-end]` seeded from the cursor or
   selection; auto-merge detection runs on commit of the resulting task.
4. **Board** — `TaskDetailScreen` renders a read-only, focusable "File Refs"
   row; pressing **Enter** opens `ait codebrowser` focused on the selected
   file:range via `launch_or_focus_codebrowser`.

The user wants (a) existing pages updated to cover these changes, and (b) a
new workflow page tying the whole story together — codebrowser selection →
new task → auto-merge — so end users can discover the feature from the
workflows index, not just from the release notes.

## Scope

In scope:
- One new workflow page that walks through the end-to-end user story.
- Targeted edits to the codebrowser, board, task-format, and aitask-create
  reference pages so each one mentions the relevant surface of the feature and
  cross-links to the workflow page.
- Keep edits forward-looking only (per the doc style memory) — no "this used
  to work differently" framing.

Out of scope:
- Opened-file history pane in codebrowser (t541 — separate feature).
- Codebrowser focus mechanism (t540_2) beyond a brief mention of how the board
  uses it.
- Any changes outside `website/content/` — no source code, no task
  description correction for the t461→t540 typo in `t565`'s description.
- Screenshots / SVGs — follow the existing `<!-- SCREENSHOT: ... -->`
  placeholder convention used elsewhere in the board/codebrowser docs; don't
  generate image assets.
- Blog post — v0.16.0 post already exists and doesn't need changes.
- Updates to Gemini CLI / Codex / OpenCode skills — t565 is a website docs
  task; per CLAUDE.md the user should create sibling tasks if they want
  corresponding updates in alt-agent skills. This is noted in the Final
  Implementation Notes but not implemented here.

## Files to modify

1. **NEW:** `website/content/docs/workflows/create-tasks-from-code.md`
2. `website/content/docs/development/task-format.md` — add `file_references`
   to the frontmatter fields table (after `folded_into` at line 48).
3. `website/content/docs/tuis/codebrowser/_index.md` — new
   "Creating Tasks from Code" section in the Tutorial (between
   "Launching an Explain Session" at line 93 and the "See also" footer at
   line 103); add a line to the "See also" bullet list pointing at the new
   workflow page.
4. `website/content/docs/tuis/codebrowser/how-to.md` — new "How to Create a
   Task from a Selection" section (insert after "How to Launch Explain from
   the Browser" ending at line 104, before "How to Navigate from Code to Task
   History").
5. `website/content/docs/tuis/codebrowser/reference.md` — add `n` row to
   the "Code Viewer" keybinding table at lines 55-65.
6. `website/content/docs/tuis/board/how-to.md` — extend the "How to Navigate
   Task Relationships" table at lines 260-268 with a "File Refs" row.
7. `website/content/docs/tuis/board/reference.md` — add `file_references` row
   to the "Task Metadata Fields" table at lines 176-196.
8. `website/content/docs/skills/aitask-create.md` — brief note on `--file-ref`
   and `--auto-merge` under "Batch Mode"; cross-link to the workflow page.

No edits to `website/content/docs/commands/` because there is no command
reference for `aitask_create.sh` there; the skill page (file 8) is the right
surface.

## Authoritative sources

Use these as the **single source of truth** for feature behavior when writing
copy — do NOT re-invent behavior. Line numbers reflect current `main`.

- **`--file-ref` entry-format grammar:**
  `aiplans/archived/p540/p540_1_foundation_file_references_field.md:22,160-166`.
  Regex: `^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$`. Example:
  `foo.py:10-20^30-40^89-100`. Exact-string dedup, order-sensitive.
- **CLI flags help text:** `.aitask-scripts/aitask_create.sh:75-83`.
- **Codebrowser `n` action:**
  `.aitask-scripts/codebrowser/codebrowser_app.py` around lines 165 and
  1033-1094 (via `aiplans/archived/p540/p540_4_codebrowser_create_from_selection.md`);
  fallback hierarchy: multi-line selection → `path:start-end`, single-line
  selection → `path:N`, no selection → `path:<cursor_line>`.
- **Auto-merge semantics + candidate discovery + safety layers:**
  `aiplans/archived/p540/p540_3_auto_merge_on_file_ref.md:90-150` and
  `.aitask-scripts/aitask_create.sh:1229-1320` (`run_auto_merge_if_needed`).
- **Interactive (finalize_draft) auto-merge prompt:**
  `aiplans/archived/p540/p540_8_finalize_draft_auto_merge_hook.md:20-80`.
- **Board `FileReferencesField`:**
  `aiplans/archived/p540/p540_5_board_file_references_field.md:58-80`.
  Read-only, Enter opens codebrowser via `launch_or_focus_codebrowser`.
- **Fold-time union:** `aiplans/archived/p540/p540_7_fold_file_references_union.md`.
- **`aitask_find_by_file.sh` contract:**
  `.aitask-scripts/aitask_find_by_file.sh`. Emits `TASK:<id>:<file>`; filters
  status to `Ready` / `Editing`; path-only matching (strips from first `:`).

## New workflow page — outline

File: `website/content/docs/workflows/create-tasks-from-code.md`

Front matter mirrors other workflow pages (e.g., `code-review.md`,
`follow-up-tasks.md`):

```yaml
---
title: "Creating Tasks from Code"
linkTitle: "Creating Tasks from Code"
weight: 65
description: "Browse source files, select a line range, and spawn a task pre-seeded with a file reference — with optional auto-merge of overlapping pending tasks."
---
```

Section order (each section 1-3 short paragraphs plus a code block or list
where useful):

1. **Why this workflow** — one short paragraph: when you spot a code smell,
   a TODO, or a bug while reading a file, you want a task that points at
   the exact lines so the implementing agent has the context without you
   having to re-find and re-paste paths. `file_references` is the structured
   home for that pointer.

2. **The `file_references` frontmatter field** — show a small YAML example
   with a plain path, a `path:N` single line, a `path:N-M` range, and a
   compact multi-range `path:N-M^N-M`. State the rules: 1-indexed inclusive,
   exact-string dedup (order-sensitive), regex-validated at CLI parse time.
   Link to `../../development/task-format` anchor.

3. **Creating a task from the codebrowser (`n`)** — the primary flow. Steps:
   - Open `ait codebrowser`, navigate to a file.
   - Optionally select lines (Shift+Up/Down or drag).
   - Press **n**.
   - An `AgentCommandScreen` opens with a pre-filled command
     `aitask_create.sh --file-ref <relpath>[:start-end]` and a title like
     "Create task — path/to/file.py (lines 10-20)".
   - Choose Run (terminal) or Run in tmux window.
   - The interactive create flow launches with a
     `Pre-populated file references: <relpath>:10-20` banner; walk through
     description → labels → metadata → finalize as usual.
   - The resulting task has `file_references: [<relpath>:10-20]` in its
     frontmatter.
   - Fallback behavior: no selection ⇒ `path:<cursor_line>`; one-line
     selection ⇒ `path:N` (not `path:N-N`).

4. **Auto-merging with existing pending tasks** — the magic. Steps:
   - After the new task commits, the create script reads back the new
     `file_references` and runs `aitask_find_by_file.sh` for each distinct
     path (path-only match; multi-range specs still match).
   - Candidate filter: only `Ready` / `Editing` tasks (folded / done /
     implementing are excluded — layer 1).
   - **Default (interactive and batch without `--auto-merge`):** warn listing
     the candidates and skip. In **interactive** mode (launched from the
     codebrowser `n` flow), a fzf Yes/No prompt asks "Fold N matching task(s)
     into tX?" first; Yes proceeds with the fold, No falls through to the
     warn-and-skip path.
   - **With `--auto-merge`:** run the three-step fold chain:
     `aitask_fold_validate.sh --exclude-self` (layer 2) →
     `aitask_fold_content.sh ... | aitask_update.sh --desc-file -` (body
     merge) → `aitask_fold_mark.sh --commit-mode fresh` (commit).
   - Fold-time `file_references` union: the primary task absorbs the folded
     tasks' `file_references` as exact-string union (no range arithmetic).
   - Include a "Safety layers" note referencing the three checkpoints.

5. **Opening a task's file refs from the board** — the reverse direction.
   Steps:
   - In `ait board`, press **Enter** on any task card to open the task
     detail dialog.
   - The "File Refs" row shows all entries verbatim
     (`[dim](none)[/dim]` if empty).
   - Focus the row (Up/Down to navigate, Tab to cycle fields) and press
     **Enter**.
   - 0 entries → no-op. 1 entry → opens codebrowser in the current tmux
     session with the file opened and the range selected. ≥2 entries →
     a picker opens first.
   - Under the hood: `launch_or_focus_codebrowser(session, entry)` in
     `lib/agent_launch_utils.py`. Requires a running tmux session for
     full "focus existing window" behavior; outside tmux it falls back
     to opening a new codebrowser process.

6. **Doing it from the command line** — for power users and automation:
   ```bash
   # Create a task from a file:line range without the codebrowser
   ./.aitask-scripts/aitask_create.sh --batch --commit \
       --name "refactor_auth" --priority medium --effort medium \
       --type refactor --labels "auth,tech-debt" \
       --file-ref "lib/auth.py:42-68" \
       --auto-merge \
       --desc "Rework the token validation path"

   # Update an existing task's file refs
   ./.aitask-scripts/aitask_update.sh --batch t42 \
       --file-ref "lib/auth.py:100-150" \
       --remove-file-ref "lib/auth.py:42-68"

   # Find pending tasks that already reference a file
   ./.aitask-scripts/aitask_find_by_file.sh lib/auth.py
   ```
   Note `--auto-merge` opt-in default (warn+skip is the safer default).
   Note `aitask_find_by_file.sh` outputs `TASK:<id>:<file>` lines.

7. **See also** — bullet links to:
   - Task Format → `file_references` field
   - Code Browser → "Creating Tasks from Code" (and reference `n`)
   - Board → "How to Navigate Task Relationships" row for File Refs
   - `/aitask-create` skill page
   - [Follow-Up Tasks workflow]({{< relref "/docs/workflows/follow-up-tasks" >}}) (sibling workflow for capturing ideas)

## Detailed edits — existing pages

### `task-format.md`
After line 48 (`folded_into`), add:
```
| `file_references` | `[path, path:N, path:N-M, path:N-M^N-M]` | Structured pointers to files / line ranges. 1-indexed, inclusive. Exact-string dedup. See [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) |
```

### `codebrowser/_index.md`
After the "Launching an Explain Session" subsection (ends line 101), insert a
new Tutorial subsection (keep it tutorial-tone, not reference):

> ### Creating Tasks from Code
>
> Press **n** to spawn a new task pre-seeded with a reference to the current
> file and selected lines. This is the primary way to capture a task with
> precise code context: navigate to the file, select a range (or just place
> the cursor on a line), press **n**, and an `AgentCommandScreen` opens with
> `aitask_create.sh --file-ref <relpath>:<start>-<end>` pre-filled. Choose
> "Run" or "Run in tmux" and the normal interactive create flow walks you
> through the remaining metadata, finishing with a committed task whose
> `file_references` frontmatter points at the exact range you chose.
>
> If the new task references a file that any existing `Ready`/`Editing` task
> already references, the create script detects the overlap and offers to
> fold those tasks into the new one — see
> [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}})
> for the full flow.

Also add one bullet to the "See also" list (lines 105-109):
```
- [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) — Workflow guide: codebrowser → file-range → task, with auto-merge
```

### `codebrowser/how-to.md`
Insert after the "How to Launch Explain from the Browser" section (ends
line 104), before "How to Navigate from Code to Task History":

> ### How to Create a Task from a Selection
>
> Capture a task whose `file_references` frontmatter points at exactly the
> lines you're looking at:
>
> 1. Open a file in the code viewer
> 2. Optionally select a range (Shift+Up/Down or mouse drag). No selection
>    is fine — the cursor line is used as a fallback
> 3. Press **n**
> 4. An `AgentCommandScreen` appears with the title
>    `Create task — <relpath> (lines N-M)` and a pre-filled command
>    `aitask_create.sh --file-ref <relpath>:N-M`
> 5. Choose **Run** (new terminal) or **Run in tmux** (tmux window).
>    You can also edit the command before running — e.g., append
>    `--auto-merge` to fold pending tasks that already reference this file
> 6. Walk through the interactive create flow as usual. At the top you will
>    see a `Pre-populated file references: <relpath>:N-M` banner
>
> The finalized task file contains
> `file_references: [<relpath>:N-M]` in its frontmatter. For the full
> story — including how auto-merge detects and folds overlapping pending
> tasks — see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}).

### `codebrowser/reference.md`
In the "#### Code Viewer" table (lines 55-65), insert a new row immediately
after the `Escape` / Clear selection row:
```
| `n` | Create a task with `file_references` seeded from the selection or cursor line | Code viewer |
```

### `board/how-to.md`
In the "How to Navigate Task Relationships" table (lines 260-268), add a row
immediately after the "Folded Into" row (line 266):
```
| **File Refs** | Opens `ait codebrowser` focused on the referenced file and line range. With 0 entries, no-op. With 1 entry, opens directly. With ≥2 entries, a picker appears first. Requires a running tmux session to reuse an existing codebrowser window. |
```

### `board/reference.md`
In the "Task Metadata Fields" table (lines 176-196), add a row after
`folded_into`:
```
| `file_references` | list | Read-only | Pointers to source files / line ranges (e.g., `foo.py:10-20`). Focused row opens `ait codebrowser` on the range. See [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}). |
```

### `skills/aitask-create.md`
Under "Batch Mode" (line 28-36), add after the existing example:

> **File references and auto-merge:**
>
> ```bash
> ./.aitask-scripts/aitask_create.sh --batch --commit \
>     --name "fix_login" --desc "..." \
>     --file-ref "lib/login.py:42-68" \
>     --auto-merge
> ```
>
> - `--file-ref PATH[:N[-M][^N[-M]...]]` (repeatable) attaches a structured
>   pointer to source lines. `--auto-merge` folds any
>   `Ready`/`Editing` task that already references the same path into the
>   new one. See the
>   [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}})
>   workflow guide for the full walkthrough, including the interactive
>   codebrowser `n` flow.

## Verification

1. **Hugo build:** `cd website && hugo --gc --minify` must succeed with no
   missing relref errors. The new page and all `{{< relref >}}` targets must
   resolve.
2. **Local serve:** `cd website && ./serve.sh`; verify:
   - `/docs/workflows/create-tasks-from-code/` renders and appears in the
     workflows sidebar
   - New entries render correctly in `task-format.md` frontmatter table and
     in `board/reference.md` / `codebrowser/reference.md` tables
   - Relative links from each edited page navigate to the new workflow page
     and back
3. **Cross-check copy against sources:**
   - `aitask_create.sh:75-83` matches the help text the doc quotes
   - The regex grammar in task-format and the workflow page matches
     `p540_1:22,160-166`
   - The interactive finalize auto-merge prompt language matches
     `p540_8:20-80` (the fzf Yes/No is only in interactive mode;
     `--batch --commit` without `--auto-merge` is silent warn+skip)
   - The board `File Refs` Enter behavior (0/1/≥2 entries, tmux session
     requirement) matches `p540_5:58-80`
4. **Style consistency:**
   - No "this used to..." phrasing (forward-only)
   - Short sections, matching the existing how-to tone
   - Screenshot placeholders use `<!-- SCREENSHOT: ... -->` (same as
     existing board/codebrowser pages); **do not** generate images
5. **Task description accuracy:** note in the final implementation notes
   (Step 8) that the task body's "see task 461" reference is actually
   t540; document the cascade of sub-tasks (t540_1 foundation, t540_3
   batch auto-merge, t540_4 codebrowser n, t540_5 board widget, t540_7
   fold union, t540_8 interactive finalize hook) for future traceability.

## Step 9 reference

Standard archival via `./.aitask-scripts/aitask_archive.sh 565` per
task-workflow Step 9. After the doc change ships, suggest the user create
sibling tasks for `.gemini/skills/`, `.agents/skills/`, and
`.opencode/skills/` if any corresponding custom commands or workflow docs
exist for alt-agent frontends — per CLAUDE.md's "WORKING ON SKILLS / CUSTOM
COMMANDS" guidance (skill changes propagate from Claude Code first).

## Final Implementation Notes

- **Actual work done:** Added one new workflow page
  `website/content/docs/workflows/create-tasks-from-code.md` (~135 lines)
  walking through the file_references field, the codebrowser `n` flow,
  auto-merge semantics (with the three safety layers: Ready/Editing filter,
  fold validator, explicit opt-in), the reverse direction from the board's
  File Refs row via `launch_or_focus_codebrowser`, and CLI examples.
  Applied 7 targeted edits to existing pages:
  - `development/task-format.md` — new row in the frontmatter fields table.
  - `tuis/codebrowser/_index.md` — new "Creating Tasks from Code" Tutorial
    subsection plus a "See also" bullet.
  - `tuis/codebrowser/how-to.md` — new "How to Create a Task from a
    Selection" section inserted between Explain and Task History sections.
  - `tuis/codebrowser/reference.md` — new `n` row in the Code Viewer
    keybinding table.
  - `tuis/board/how-to.md` — new "File Refs" row in the Navigate Task
    Relationships table.
  - `tuis/board/reference.md` — new `file_references` row in the Task
    Metadata Fields table.
  - `skills/aitask-create.md` — new "File references and auto-merge" block
    under Batch Mode with a cross-link to the workflow page.
- **Deviations from plan:** None of substance. Two minor wording choices:
  wrote the relationship-table description as "2+ entries" instead of the
  "≥2 entries" in the plan outline (plain ASCII reads better across the
  existing tables), and the board reference row mentions pressing **Enter**
  on a focused row (slightly more specific than the plan text). The new
  workflow page uses `2+` in its dispatch table for the same reason.
- **Issues encountered:** After running `hugo --gc --minify` inside
  `website/`, the shell was still in that directory when the Step 8 plan
  externalization call ran, which made the relative script path fail. Fixed
  by running the script with an absolute `cd /home/ddt/Work/aitasks &&`
  prefix. Not a plan issue — just a sequencing nit.
- **Key decisions:**
  - Kept the doc forward-only per the memory: no "this used to..." framing,
    no references to t461/t540 in the reader-facing copy.
  - Treated the codebrowser `n` flow as the primary path and the CLI flags
    as the power-user alternative, matching how `aitask-explore` and other
    workflow pages present dual interactive/batch surfaces.
  - Did not generate screenshots. Left no placeholders either — the
    existing workflow pages (`follow-up-tasks.md`, `capturing-ideas.md`) do
    not embed screenshots, so the new page follows their style.
  - Did not touch `_index.md` in `workflows/` — it is a bare section index
    and discovery works via the Docsy sidebar + weight frontmatter.
- **Verification results:** `cd website && hugo --gc --minify` succeeds
  with 131 pages rendered, no relref errors, no missing-page warnings.
- **Alt-agent follow-up:** t565 touches only website docs, so there is no
  Gemini CLI / Codex CLI / OpenCode skill version to update. The user may
  still want a sibling task to port any future changes to the corresponding
  alt-agent skill docs if/when those exist.
