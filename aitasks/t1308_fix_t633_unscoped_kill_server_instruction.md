---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, manual_verification]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 633
implemented_with: claudecode/opus5
created_at: 2026-07-28 19:15
updated_at: 2026-08-04 17:25
boardidx: 76800
---

## Problem

`aitasks/t633_manual_verification_force_exact_tmux_targeting_followup.md`
opens its verification checklist with:

```
- [ ] tmux kill-server to clear all sessions
```

That instruction is **unscoped**, and since t953 it is both dangerous and wrong:

- Bare `tmux kill-server` targets the user's **personal/default** tmux server.
- `ait` sessions live on the dedicated **`-L ait`** socket (t953, landed
  2026-06-11 in `1b915a426`; see `AIT_DEDICATED_SOCKET` in
  `.aitask-scripts/lib/tmux_exec.py` and `lib/tmux_exec.sh`).

So a person following the checklist literally **kills every pane in their
personal tmux** — including any code agents running there — while leaving the
`ait` sessions the step is trying to clear completely untouched. It is
destructive to the wrong target *and* ineffective for its stated purpose.

t633 was created 2026-04-23, roughly seven weeks before the dedicated socket
landed, so the instruction was correct when written and silently rotted.

## Fix

Rewrite the checklist item to name the socket the rest of the checklist
actually exercises (`ait ide` → `-L ait`):

```
- [ ] `tmux -L ait kill-server` to clear all ait sessions (NOT bare
      `tmux kill-server` — that targets your personal tmux server and leaves
      the ait sessions running)
```

Then re-read the remaining items in that checklist for the same rot: anything
that says plain `tmux <verb>` should be checked against whether it means the
dedicated server. In particular `tmux list-sessions` (item 5) has the same
problem — it will not list ait sessions.

Honour `AITASKS_TMUX_SOCKET` if the checklist is meant to be portable: unset →
`-L ait`, non-empty → `-L <value>`, `default` → the user's default server
(semantics in `lib/tmux_exec.py:70-89`).

## Scope

Task-data only — this edits a markdown checklist, no code. Commit with
`./ait git`.

## Acceptance criteria

- No bare `tmux kill-server` remains in t633's checklist.
- Every tmux command in that checklist is explicit about which server it targets.
- The intent of the original step (start from a clean slate of ait sessions) is
  preserved.

## Why this is not labelled `tmux_destructive`

Performing this fix is a markdown edit and destroys nothing. The *task being
fixed* (t633) carries the label; this one does not.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T14:25:10Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-04T14:35:07Z status=pass attempt=1 type=human
