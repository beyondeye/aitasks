---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: []
anchor: 1580
followup_kind: review_finding
created_at: 2026-08-24 13:21
updated_at: 2026-08-24 13:21
---

## Problem

`t1580` promoted the unconfigured-repo tmux session fallback to a named constant,
`DEFAULT_TMUX_SESSION` in `.aitask-scripts/lib/agent_launch_utils.py`, and routed
`_read_default_session`'s two return sites through it.

`.aitask-scripts/applink/server.py:39` keeps its own `DEFAULT_SESSION = "aitasks"`
— the same value, spelled independently. t1580 left it alone deliberately: applink
is a standalone LAN listener and importing the launcher module for one string is a
real cost, so the two were left as separate literals with a cross-referencing
comment on each side.

Nothing enforces the equality. If `DEFAULT_TMUX_SESSION` ever changes, applink
keeps the old value silently.

## The actual question

This is a **decision** task first, an implementation task second. Whether these two
constants are one contract or two independent defaults is genuinely open:

- **One contract** — they describe the same thing (the session name an
  unconfigured repo uses), so they should never disagree. Enforce it: either
  applink imports the constant, or a drift guard pins them equal.
- **Two defaults** — applink's is the default *its own listener* advertises when
  no session is given, which is not necessarily the same concept as the launcher's
  config fallback even though the value coincides today. Then the right answer is
  to document them as unrelated and drop the cross-references, so no one later
  "fixes" a drift that was never a bug.

Answer that before writing code. A drift guard added without deciding this just
freezes an accidental coincidence.

## Why it is filed separately

A guard for this was written during t1580 implementation and rejected in review:
it imported `applink/server.py` from `tests/test_minimonitor_own_header_session.py`,
which would have created the shared contract as a side effect of a minimonitor
header test rather than recording a decision to have one. If a guard is wanted it
belongs in an applink- or launcher-focused test module.

## Acceptance criteria

- The question above is answered explicitly, with the reasoning recorded.
- If "one contract": the equality is enforced (import or drift guard), and the
  guard lives in an applink- or launcher-focused test module — never in a
  minimonitor/TUI test.
- If "two defaults": the cross-referencing comments in
  `.aitask-scripts/applink/server.py` and (if present) `agent_launch_utils.py` are
  rewritten to say the values are independent and may diverge.
- Either way, no comment is left claiming an enforcement that does not exist.

## Context

- t1580 — `aiplans/archived/p1580_*.md`, post-phase 2a.
- `.aitask-scripts/lib/agent_launch_utils.py` — `DEFAULT_TMUX_SESSION`,
  `_read_default_session`, `AitasksSession.key` (why the value is not unique).
- `.aitask-scripts/applink/server.py:39` — `DEFAULT_SESSION`.
