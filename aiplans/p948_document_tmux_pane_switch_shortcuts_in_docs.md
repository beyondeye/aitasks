---
Task: t948_document_tmux_pane_switch_shortcuts_in_docs.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Document tmux pane-switching shortcuts (t948)

## Context

New users (and even experienced ones) only learn the *intra-window* pane
navigation that aitasks builds itself: minimonitor's **Tab** jumps focus
**minimonitor → agent pane**. There is no built-in keybinding for the reverse
direction (agent pane → minimonitor) — for that the user must fall back on
the native tmux shortcuts **`Ctrl-b o`** (cycle to the next pane) and
**`Ctrl-b` + arrow keys** (move focus directionally). These are never
documented, so users resort to clicking the minimonitor pane to activate it.

This task adds short documentation of these native tmux shortcuts in two
website pages so the both-directions navigation story is complete.

**Framing (per user steer):** the docs must (a) be explicit that these are
native **tmux** shortcuts for moving between **panes within one tmux
window**, and (b) clarify that intra-window pane-switching is **mostly only
relevant for the minimonitor case** — every other ait TUI (board, monitor,
codebrowser, settings, brainstorm) fills its **whole tmux window** as a single
pane, so there is nothing to switch *to* inside the window. Minimonitor is the
one situation that puts two panes (agent + minimonitor sidebar) in the same
window. For moving between the full-window TUIs you switch tmux **windows**
(via `j` / the TUI switcher), not panes.

## Changes

### 1. `website/content/docs/getting-started.md`

Add a short note teaching new users how to move focus *between panes in a
window* (distinct from `j`, which switches between TUI **windows**). The
natural anchor is **§2 "Start the ait IDE"**, right after the existing `j`
TUI-switcher paragraph (currently around line 35–37, before the "Can't use
tmux?" blockquote).

Insert a new short paragraph, e.g.:

> `j` switches between tmux **windows**. To move focus **between panes inside
> a single tmux window**, use the native tmux shortcuts **`Ctrl-b o`** (cycle
> to the next pane) or **`Ctrl-b` + an arrow key** (move directionally). This
> mostly matters for the **minimonitor** sidebar, which splits an agent
> window into an agent pane and a minimonitor pane — every other ait TUI
> (board, monitor, codebrowser, settings, brainstorm) fills its whole tmux
> window, so you move between those with `j` instead. `Ctrl-b` is the default
> tmux prefix; if you remapped your prefix, substitute your own.

Keep it brief and current-state-only (no version history), per
`aidocs/framework/documentation_conventions.md`.

### 2. `website/content/docs/tuis/minimonitor/how-to.md`

The existing **"How to Focus the Sibling Agent Pane"** section (lines 65–69)
documents **Tab** (minimonitor → agent pane). Add a new subsection
immediately after it covering the reverse direction via native tmux, e.g.:

```markdown
### How to Focus Minimonitor from the Agent Pane (native tmux)

**Tab** only goes one way: minimonitor → agent pane. There is no built-in
shortcut for the opposite direction. Because minimonitor lives as a second
pane inside the agent's tmux **window**, you move focus the other way (agent
pane → minimonitor) with tmux's own pane-switching keys — the same keys you
would use to move between any two panes in one window:

- **`Ctrl-b o`** — cycle tmux focus to the next pane in the window.
- **`Ctrl-b` + an arrow key** — move focus directionally to the adjacent pane.

This also saves you from clicking the minimonitor pane to activate it.
`Ctrl-b` is the default tmux prefix; if you remapped your prefix, substitute
your own. Once you are comfortable with these native shortcuts you can use
them for **both** directions instead of Tab if you prefer.

(This intra-window pane switching is specific to the minimonitor split — the
other ait TUIs each occupy their own full tmux window, which you reach with
`j` / the [TUI switcher](#how-to-jump-to-another-tui).)
```

Also add a row to the **Key Bindings Quick Reference** table (lines 159–169)
documenting the native tmux shortcuts as an external/native option — phrased
so it's clear these are tmux's own keys, not minimonitor keybindings (e.g. a
note row: `` `Ctrl-b o` / `Ctrl-b` + arrow | (native tmux) Focus the other
pane in this window — works both directions ``). Alternatively keep them out
of the per-key table and reference them in prose only if a table row reads
awkwardly; the prose subsection is the primary deliverable.

**Wording alignment:** the monitor how-to's "How to Switch tmux to the
Focused Pane" section is already cross-referenced from the "Pairing
Minimonitor with Monitor" section (line 140). That section covers monitor's
`s` key (a different mechanism — cross-window switch), so no new
cross-reference is required; just keep terminology consistent ("tmux focus",
"pane in this window").

## Verification

- `cd website && hugo build --gc --minify` (or `./serve.sh` for local
  preview) builds without errors and the two pages render the new content.
- Manually read both rendered pages to confirm wording reads naturally and
  the keybinding table (if a row was added) is not misleading about
  native-vs-minimonitor keys.
- No code paths touched — no unit/shell tests apply.

## Step 9 (Post-Implementation)

Docs-only change on the current branch (no worktree/branch created). After
review + commit, archive via `./.aitask-scripts/aitask_archive.sh 948` and
push per the shared workflow Step 9.

## Risk

### Code-health risk: low
- None identified. Documentation-only change to two Markdown pages; no code,
  scripts, or config touched; zero blast radius beyond the rendered website.

### Goal-achievement risk: low
- None identified. Requirements are explicit (exact pages, shortcuts, and
  placement named in the task); target files and anchors already verified to
  exist.
