---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [docs]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-08 17:38
updated_at: 2026-06-08 18:05
completed_at: 2026-06-08 18:05
---

Document the native tmux pane-switching shortcuts — **`Ctrl-b o`** (cycle to the next pane) and **`Ctrl-b` + arrow keys** (move focus directionally) — and explain how to use them, in two website doc pages:

1. **Getting Started** — `website/content/docs/getting-started.md`: add a short note introducing these tmux shortcuts so new users learn how to move focus between panes in a window from the start.

2. **Minimonitor** — `website/content/docs/tuis/minimonitor/how-to.md`: this is the most useful place. The minimonitor pane already supports **`Tab`** to switch focus *from* minimonitor *to* the associated code-agent pane (see the existing Tab section around line 67 and the keybindings table around line 162). But there is no built-in shortcut for the *opposite* direction (agent pane → minimonitor); for that the user needs the native tmux shortcuts. Document that:
   - `Tab` covers minimonitor → agent pane.
   - To go the other way (agent pane → minimonitor), or to avoid clicking the minimonitor pane to activate it, use `Ctrl-b o` or `Ctrl-b` + arrow key.
   - Once a user is acquainted with the native tmux shortcuts, they can use them for **both** directions if they prefer, instead of `Tab`.

Notes:
- The monitor how-to already has a "How to Switch tmux to the Focused Pane" section (cross-referenced from minimonitor how-to line 140) — align wording/cross-references with it where relevant.
- Follow `aidocs/framework/documentation_conventions.md` (current-state-only prose, no version history).
- `Ctrl-b` is the default tmux prefix; mention that users who remapped their prefix should substitute their own.
