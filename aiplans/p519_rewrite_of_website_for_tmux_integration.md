---
Task: t519_rewrite_of_website_for_tmux_integration.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# t519 — Rewrite website docs for the new tmux integration

## Context

The ait framework has evolved into a tmux-based "IDE" for agentic coding: `ait monitor` (orchestrator TUI), `ait minimonitor` (sidebar), a TUI switcher triggered with `j`, plus `ait board`, `ait codebrowser`, `ait settings`, `ait brainstorm` — all navigable from one another via the switcher and all running as tmux windows inside a single session.

The current website documentation does not reflect this. Specifically:

- `website/content/docs/installation/terminal-setup.md` mischaracterizes tmux as a terminal emulator alongside Ghostty/WezTerm/Warp and describes a generic "multi-tab terminal workflow". tmux is a multiplexer that *runs inside* a terminal emulator — the docs are wrong.
- There is **no documentation** for `ait monitor`, `ait minimonitor`, or the `j` TUI switcher. The `tuis/_index.md` overview only lists Board, CodeBrowser, Settings.
- Getting Started never mentions tmux at all.
- The 4-step startup (terminal → cd → tmux → `ait monitor`) is bad UX, partly because when tmux starts without a session name, monitor has to offer a `SessionRenameDialog` as a fallback.

This task rewrites the relevant website pages, adds new docs for the previously undocumented TUIs and the switcher, and adds a new `ait ide` subcommand that collapses the 4-step startup into one command with a correct session name from the start.

## Fold scope

- **t494** — **folded** into t519. Scope: (a) document the `j` "TUI switcher" shortcut in each TUI's docs under a new "tmux integration" section; (b) rename the footer binding label from "Jump TUI" to "TUI switcher" in `.aitask-scripts/lib/tui_switcher.py`.
- **t475_5** — **NOT folded** (user explicitly excluded during planning). No implementation and no documentation of t475_5 scope.

## Out of scope / follow-ups

- **Screenshots.** Docs are written text-only with HTML comment placeholders (`<!-- TODO screenshot: aitasks_<feature>.svg -->`). A follow-up task will be created at archival for capturing SVGs for TUI switcher dialog, `ait monitor`, `ait minimonitor`, the settings tmux tab, and `ait ide` startup.
- **diffviewer TUI** is intentionally not documented. Per user direction, diffviewer is a transitional TUI that will be integrated into the brainstorm TUI at a later stage. The TUI switcher still lists it for functional reasons, but it is omitted from all user-facing documentation in t519.

## Approach: parent with 6 children + 1 follow-up

t519 becomes a parent with six child subtasks. Auto-sibling dependencies give the right serialization. The critical path is t519_1 (the new `ait ide` subcommand), because later doc children reference the command by name.

All child task files live under `aitasks/t519/` and child plans under `aiplans/p519/`. The follow-up screenshot task is created as a standalone parent task at t519 archival time.

### Order of implementation

1. **t519_1** — new `ait ide` subcommand (code + dispatcher + commands reference). Blocker for t519_2 and t519_3.
2. **t519_2** — rewrite `installation/terminal-setup.md` (needs `ait ide`).
3. **t519_3** — update `getting-started.md` + add `workflows/tmux-ide.md` (needs `ait ide`).
4. **t519_4** — create `tuis/monitor/` docs (independent; can parallelize with t519_1 in principle, but auto-sibling deps will serialize it).
5. **t519_5** — create `tuis/minimonitor/` docs.
6. **t519_6** — update `tuis/_index.md`, add "tmux integration" + `j`-shortcut sections to each TUI's how-to (board, codebrowser, settings, brainstorm), rename footer label in `lib/tui_switcher.py` (folded t494 scope).

See each child plan in `aiplans/p519/` for detailed implementation steps.

## Cross-cutting conventions

- **Screenshot placeholders:** use HTML comments like `<!-- TODO screenshot: aitasks_monitor_main.svg -->`. Do **not** use `{{< static-img src="..." >}}` shortcodes with missing files.
- **Hugo weights:** new pages in `tuis/` and `workflows/` must pick `weight:` values deliberately; check siblings before choosing.
- **Hugo aliases:** do **not** add `aliases:` front-matter on new pages unless you've verified they don't collide with existing aliases. Hugo fails to build on duplicate aliases.
- **Docsy headings:** do not rename existing H2 headings (auto-generated anchors may be linked externally).
- **Screenshots follow-up task:** at the very end of t519 archival, create a new parent task listing the SVGs to capture and the exact `.md` file + section for each.

## Whole-task verification (at archival time)

- `cd website && hugo --gc --minify` builds cleanly with no broken links or missing-image errors.
- `./serve.sh` local dev server renders all new pages correctly in the sidebar.
- `ait ide` from a plain shell starts tmux with the configured session name and launches monitor (covered by t519_1 child verification).
- Manual spot-check: each TUI's footer shows "TUI switcher" on the `j` binding.
- `shellcheck .aitask-scripts/aitask_ide.sh` passes.
- Any existing tests in `tests/` that reference the "Jump TUI" label string pass after the rename.

## Step 9 — Post-Implementation

On completion of the last child, the shared workflow's Step 9 (Post-Implementation) archives children, archives the parent, and runs the commit sequence. The screenshot follow-up task is created at that time via `aitask_create.sh --batch` with a full list of (target SVG, target `.md` file, target section).
