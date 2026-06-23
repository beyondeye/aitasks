---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-23 14:27
updated_at: 2026-06-23 14:37
---

## Problem

In the `ait brainstorm` TUI, the single-key tab-switch bindings only fire while
the **Browse** tab is active. From the **Session** or **Running** tab, pressing
`b` / `g` / `d` / `s` / `r` does not switch tabs — the user is stuck on the
current tab and must use another mechanism (e.g. the command palette) to get
back to Browse. Switching works fine *from* Browse (Browse → Session via `s`,
Browse → Running via `r`), but not back.

A related symptom: the footer keeps showing **Browse-scoped** action labels
(`⏎ Open detail`, `A Node action`, `f Defer module`) while the Session/Running
tab is active, suggesting `check_action` / binding-context evaluation is not
re-running per active tab.

## Reproduction

1. `ait brainstorm <session>` (boots on Browse).
2. Press `r` → Running tab (works).
3. Press `b` (or `g`/`d`/`s`) → **nothing happens; still on Running**.
   Same from the Session tab.

Verified live in session t1017 driven via tmux send-keys/capture-pane.

## Not a regression

This is **pre-existing**, NOT introduced by the t1048 brainstorm
modularization. Reproduced identically on the pre-t1048 parent commit
`dcabff063` (a throwaway worktree): `b` from the Running tab also fails to
return to Browse there. Surfaced during the t1052 live smoke test of t1048.

## Investigation pointers (all in `.aitask-scripts/brainstorm/brainstorm_app.py`)

- Tab-switch bindings: `Binding("b", "tab_browse")`, `"d"`/`"g"` (Browse
  variants), `"s"`/`"r"` (Session/Running) — around lines 2044-2060.
- Action handlers: `action_tab_browse` (~2695), `action_tab_session` (~3054),
  `action_tab_running` (~3060). Each just sets
  `self.query_one(TabbedContent).active = ...`; they are NOT guarded against
  the current tab.
- `check_action` (~2171) and `_TAB_SCOPED_ACTIONS` (~2079): the tab-switch
  actions are NOT listed in `_TAB_SCOPED_ACTIONS`, so they should return
  `True` everywhere — yet they only fire from Browse. The focused widget on
  Session/Running (OperationRow / GroupRow, both `can_focus`) is a likely
  factor, though neither defines an `on_key` that consumes letter keys
  (OperationRow only handles left/right; GroupRow/AgentStatusRow/ProcessRow
  have none). The stale footer points at binding-context not re-evaluating
  when the active tab changes.

## Acceptance criteria

- `b` / `g` / `d` / `s` / `r` switch tabs from **any** active tab (Browse,
  Session, Running), not only from Browse.
- The footer reflects the active tab's scoped actions (no Browse-only labels
  leaking onto Session/Running).
- Add/extend a test that exercises tab switching from each tab (the brainstorm
  suite already boots the live TUI).
