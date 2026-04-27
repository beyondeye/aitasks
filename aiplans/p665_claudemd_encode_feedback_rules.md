---
Task: t665_claudemd_encode_feedback_rules.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Encode 8 user-feedback rules into CLAUDE.md (t665)

## Context

Parent task t664 is reviewing the auto-memory feedback files in
`~/.claude/projects/-home-ddt-Work-aitasks/memory/` and converting each into a
durable codebase artifact so future Claude Code sessions have the context
without depending on auto-memory (which is being deleted). t665 covers the
subset that should land in `CLAUDE.md` — eight rules with their `**Why:**` and
`**How to apply:**` blocks intact.

The task description already provides the full verbatim text for each
addition. This plan covers placement and formatting decisions only.

## Design decisions

1. **CLI Conventions placement (resolved with user):** Add a new top-level
   `## CLI Conventions` H2 section between `## Shell Conventions` and
   `## Commit Message Format`. Keeps `ait` verb-naming rules separate from
   shell-portability rules, since they have different audiences (framework
   maintainers vs script authors).

2. **Bullet formatting:** Each addition becomes a single bulleted list item
   in its target section, with:
   - First line: bold short rule statement (`- **Rule headline.**`)
   - Body: prose paragraph(s) followed by `**Why:**` block and
     `**How to apply:**` block, indented as continuation under the bullet.
   The task description prescribes "short bullet headers, **Why:** and
   **How to apply:** lines for rules" — this matches existing CLAUDE.md
   bullet style while preserving the auto-memory rule structure.

3. **In-section ordering:** New bullets append after existing bullets in
   each section. Within the four new TUI bullets, ordered keybinding-first,
   tmux-architectural-second:
   1. Pane-internal cycling uses `←` / `→`
   2. TUI switcher shortcuts act on selected session
   3. Single tmux session per project
   4. Companion pane auto-despawn

## Critical files

Only one file changes:

- `/home/ddt/Work/aitasks/CLAUDE.md` — eight bullet additions across four
  sections plus one new H2 section.

## Insertion targets (line refs from current `CLAUDE.md`)

| # | Section | Insertion point | Bullets to add |
|---|---------|-----------------|----------------|
| 1 | TUI (Textual) Conventions (lines 143–148) | After last existing bullet (line 148) | 4 new bullets |
| 2 | Skill / Workflow Authoring Conventions (lines 172–175) | After last existing bullet (line 175) | 1 new bullet |
| 3 | Adding a New Helper Script (lines 82–96) | After existing closing paragraph (line 96) | 1 new bullet (or short `####` sub-section) |
| 4 | New `## CLI Conventions` H2 | Between line 115 (end of Shell Conventions) and line 117 (`## Commit Message Format`) | 2 new bullets |

Total: 4 + 1 + 1 + 2 = 8 additions, mapping 1:1 to the eight feedback memories.

## Implementation steps

1. **Edit 1 — TUI Conventions section.** Append the four new bullets in the
   order specified above. Each bullet uses the exact prose, `**Why:**`, and
   `**How to apply:**` text from the task description (sections 1.a–1.d).

2. **Edit 2 — Skill / Workflow Authoring Conventions section.** Append a third
   bullet using the exact text from task section 2 ("Context-variable pattern
   over template substitution").

3. **Edit 3 — Adding a New Helper Script section.** Append the "Test the full
   install flow" content from task section 3, formatted to match the existing
   `**Codex exception:** …` paragraph style (bold-lead then prose). This
   section already mixes paragraphs and a final "When splitting…" summary; the
   new content slots in before that summary or as a `####` sub-section. Use a
   `#### Test the full install flow` sub-heading to mirror the
   `#### a/b/c/d` style hinted at in the task description, since this content
   is too long to read well as a single paragraph.

4. **Edit 4 — Insert new H2 `## CLI Conventions`** between Shell Conventions
   and Commit Message Format. Two bullets:
   - `**ait setup vs ait upgrade**` (task section 4.a)
   - `**CLI verb rename: clean removal preferred**` (task section 4.b)

5. **Sanity check the diff:**
   ```bash
   git diff CLAUDE.md | head -300
   git diff --stat
   ```
   Expect: `CLAUDE.md` is the only modified file.

## Verification

- `git diff CLAUDE.md` shows exactly four touched regions:
  TUI Conventions, Skill / Workflow Authoring Conventions,
  Adding a New Helper Script, and a new `## CLI Conventions` block.
- `git diff --stat` shows `CLAUDE.md` as the only changed file.
- Read the rendered file end-to-end: each new bullet sits under the right
  section header; new H2 lives between Shell Conventions and Commit Message
  Format; existing bullets and paragraphs are unchanged in wording.
- Spot-check that `**Why:**` and `**How to apply:**` markers are preserved
  verbatim in every new bullet.
- Confirm no auto-memory file paths are referenced as authoritative — content
  is fully self-contained in `CLAUDE.md`.

## Step 9 (Post-Implementation)

After commit, follow the standard task-workflow Step 9 archival flow:
- No worktree to clean up (worked on current branch).
- No build verification (`verify_build` not configured).
- Run `./.aitask-scripts/aitask_archive.sh 665`.
- Push with `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Added 7 of the 8 planned bullets to `CLAUDE.md` across the four targeted regions:
  - TUI Conventions: 4 bullets (pane-internal cycling, TUI-switcher selected-session, single tmux session per project, companion pane auto-despawn). All retain `**Why:**` and `**How to apply:**` blocks.
  - Skill / Workflow Authoring Conventions: 1 bullet (context-variable pattern over template substitution engines). Retains `**Why:**` and `**How to apply:**` blocks.
  - Adding a New Helper Script: 1 `#### Test the full install flow for setup helpers` subsection with `**Why:**` and `**How to apply:**` blocks.
  - New `## CLI Conventions` H2 (between Shell Conventions and Commit Message Format): 1 bullet for `ait setup` vs `ait upgrade`, with `**How to apply:**` only.
- **Deviations from plan:** During the Step 8 review the user trimmed the new CLI Conventions section before approving the commit:
  1. Removed the second bullet entirely ("CLI verb rename: clean removal preferred over deprecated alias"). The rule is no longer encoded in `CLAUDE.md`; it remains documented in the source task file (t665) and the auto-memory file it came from.
  2. Removed the `**Why:**` block from the surviving "ait setup vs ait upgrade" bullet. The rule statement and `**How to apply:**` remain.
  Net: 7 bullets, +61 lines (vs. planned 8 bullets, +72 lines). The Step-8 system reminder explicitly flagged this as an intentional change to preserve.
- **Issues encountered:** None blocking. Two minor corrections during execution: (a) the externalize helper script is `aitask_plan_externalize.sh` (not `aitask_externalize_plan.sh`); (b) multiple internal plan files existed in `~/.claude/plans/`, so disambiguation required `--internal <path>`.
- **Key decisions:**
  - CLI Conventions placed as a new top-level H2 (option chosen via AskUserQuestion before plan write), not as bullets under Shell Conventions, to keep `ait` verb-naming rules separate from shell-portability rules.
  - In-section ordering for the new TUI bullets: keybinding-first (pane cycling, TUI switcher), then tmux-architectural (single session, companion auto-despawn).
