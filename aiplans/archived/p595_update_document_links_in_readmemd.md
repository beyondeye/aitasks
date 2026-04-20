---
Task: t595_update_document_links_in_readmemd.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Update documentation map in README.md (t595)

## Context

The "📖 Documentation" section at the end of the main repo `README.md` (lines 112–128) was written before the recent repositioning of aitasks as *"a full agentic IDE in your terminal"*. The current tagline (line 8) and feature list (lines 32–45) advertise the agentic IDE framing, but the documentation map at the bottom still treats the project as a narrow "kanban + skills" tool and misses newer top-level documentation sections.

Concrete drift vs. the current website tree (`website/content/docs/`):

1. **"Kanban Board" → `https://aitasks.io/docs/board/`** — the docs moved under `/docs/tuis/board/` (old URL still redirects via the `aliases:` entry in `tuis/_index.md`). Worse, the link advertises only the Board, but the site now documents a full TUI suite: **Monitor**, **Minimonitor**, **Board**, **Code Browser**, **Settings**, and **Brainstorm** (all under `/docs/tuis/`). This is the headline evidence of the "agentic IDE" positioning and should be the one that replaces the "Kanban Board" link.

2. **"Claude Code Skills" → `https://aitasks.io/docs/skills/`** — the website page is titled "Code Agent Skills" (see `website/content/docs/skills/_index.md`) because the framework now supports Claude Code **and** Gemini CLI, Codex CLI, and OpenCode. The README should match.

3. **Missing: Overview** (`/docs/overview/`) — a top-level page that states the IDE positioning, the challenge it addresses, and the core philosophy. It was added as a navigational landing for the positioning.

4. **Missing: Concepts** (`/docs/concepts/`) — a now-sizeable section covering tasks, plans, parent/child, folded tasks, review guides, execution profiles, verified scores, agent attribution, locks, task lifecycle, plans, agent memory, git branching model, IDE model. This is where readers learn *what each building block is*.

Per CLAUDE.md, user-facing docs must describe **current state only** — so the update replaces the outdated entries in place without any "previously…"/"used to be…" prose.

Per the project note in `CLAUDE.md`, `diffviewer` is transitional and must **not** be listed in user-facing lists of TUIs — only board, monitor, minimonitor, codebrowser, settings, brainstorm are documented.

## Scope

Edit exactly one file: `README.md`, lines 112–128 (the `## 📖 Documentation` section). No other files change.

## Target Content

Replace the current Documentation section body (lines 112–128) with:

```markdown
## 📖 Documentation

**[Documentation Website](https://aitasks.io/)** — Browse the full documentation online.

- **[Overview](https://aitasks.io/docs/overview/)** — The challenge aitasks addresses, its core philosophy, and key features of the agentic IDE.

- **[Installation](https://aitasks.io/docs/installation/)** — Quick install, platform support, setup, and git remote authentication.

- **[Getting Started](https://aitasks.io/docs/getting-started/)** — First-time walkthrough from install to completing your first task.

- **[Concepts](https://aitasks.io/docs/concepts/)** — What each building block is and why it exists: tasks, plans, parent/child, folded tasks, review guides, execution profiles, verified scores, agent attribution, locks, and the IDE model.

- **[TUI Applications](https://aitasks.io/docs/tuis/)** — The terminal IDE: Monitor, Minimonitor, Board, Code Browser, Settings, and Brainstorm — hop between them with a single keystroke via `ait ide`.

- **[Workflow Guides](https://aitasks.io/docs/workflows/)** — End-to-end guides for common usage patterns: capturing ideas fast, tmux IDE, complex task decomposition, parallel development, code review, QA, PR workflow, and more.

- **[Code Agent Skills](https://aitasks.io/docs/skills/)** — Reference for `/aitask-pick`, `/aitask-explore`, `/aitask-create`, and other skill integrations across Claude Code, Gemini CLI, Codex CLI, and OpenCode.

- **[Command Reference](https://aitasks.io/docs/commands/)** — Complete CLI reference for all `ait` subcommands.

- **[Development Guide](https://aitasks.io/docs/development/)** — Architecture overview, directory layout, library scripts, and release process.
```

Summary of changes per bullet:

| Change | Before | After | Reason |
|--------|--------|-------|--------|
| Added | — | Overview | New landing page for the agentic-IDE positioning |
| Added | — | Concepts | Sizeable new doc section; users can't find it from the README otherwise |
| Renamed + repointed | "Kanban Board" → `/docs/board/` | "TUI Applications" → `/docs/tuis/` | The section now documents the full IDE (6 TUIs); old URL still redirects but title is misleading |
| Renamed | "Claude Code Skills" | "Code Agent Skills" | Website page title; reflects multi-agent support (Claude Code, Gemini CLI, Codex CLI, OpenCode) |
| Tweaked description | Workflow Guides (generic list) | Added tmux IDE, code review, QA, PR workflow | Highlights workflow breadth that the agentic-IDE framing implies |
| Unchanged | Installation, Getting Started, Command Reference, Development Guide | (same) | Still accurate |

## Order rationale

Ordering mirrors the website sidebar's `weight:` values: Overview (5) → Installation (10) → Getting Started (15) → Concepts (25) → TUIs (30) → Workflows (40) → Skills (50) → Commands (60) → Development (70). The reader hits the IDE positioning in the right flow (overview → install → first task → concepts → IDE surface → workflows → skills → CLI → internals).

## Critical files to modify

- `README.md` — lines 112–128 only.

## Verification

1. **Render locally** — open `README.md` in a preview (GitHub-flavored markdown) and confirm all 9 bullet links render and match the table above.
2. **Link liveness** — each link resolves to a valid page on the current website tree:
   - `/docs/overview/` → `website/content/docs/overview.md` ✅
   - `/docs/installation/` → `website/content/docs/installation/` ✅
   - `/docs/getting-started/` → `website/content/docs/getting-started.md` ✅
   - `/docs/concepts/` → `website/content/docs/concepts/_index.md` ✅
   - `/docs/tuis/` → `website/content/docs/tuis/_index.md` ✅
   - `/docs/workflows/` → `website/content/docs/workflows/_index.md` ✅
   - `/docs/skills/` → `website/content/docs/skills/_index.md` ✅
   - `/docs/commands/` → `website/content/docs/commands/_index.md` ✅
   - `/docs/development/` → `website/content/docs/development/_index.md` ✅
3. **Text check** — link titles match the `title:` frontmatter of each target `_index.md` (or the conceptual name) so the README and site navigation tell the same story.
4. **Forward-only prose** — grep the diff for any "previously", "used to", "earlier", "now" prose; the CLAUDE.md "current state only" rule is enforced.
5. **diffviewer guard** — grep the diff to confirm `diffviewer` is not introduced as a user-facing TUI (per the project-specific note in CLAUDE.md).

## Post-implementation (Step 9)

Standard single-task flow:
- Step 8 review → commit as `documentation: Update README documentation map for agentic IDE positioning (t595)`.
- Step 9 archive via `./.aitask-scripts/aitask_archive.sh 595`.
- Push via `./ait git push`.

No worktree cleanup (work was on current branch per `create_worktree: false` in the `fast` profile).

## Final Implementation Notes

- **Actual work done:** Replaced lines 112–128 of `README.md` as planned. Resulting section now has 9 bullets (was 7): Overview (new), Installation, Getting Started, Concepts (new), TUI Applications (replaces "Kanban Board"), Workflow Guides (with expanded description mentioning tmux IDE, code review, QA, PR), Code Agent Skills (renamed from "Claude Code Skills"), Command Reference, Development Guide. Ordering mirrors the website sidebar `weight:` values.
- **Deviations from plan:** None. The target content was applied verbatim.
- **Issues encountered:** None.
- **Verification performed:** Ran `git diff README.md | grep -iE '(previously|used to|earlier|diffviewer)'` — returned no matches (PASS). Link paths cross-checked against `website/content/docs/` tree during planning; all nine targets exist. Diff is +7/-3 lines.
- **Key decisions:** Kept the "Claude Code Skills → Code Agent Skills" rename ahead of leaving the old heading; the website page is already titled "Code Agent Skills" and the repositioning calls out multi-agent support (Claude Code, Gemini CLI, Codex CLI, OpenCode). Replaced "Kanban Board" with "TUI Applications" linking to `/docs/tuis/` so the IDE surface is visible from the README without needing a redirect.
