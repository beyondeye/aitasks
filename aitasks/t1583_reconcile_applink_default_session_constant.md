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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1811** id=2026-09-17T06:15:40Z.6cc66e47081d926e40fa2e01 from=t1811 from_verified=yes at=2026-09-17T06:15:40Z base=bc97800ee96fd5b0349c3bb65edd3395efec4aba base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1811 (commit bc97800ee), relevant to your "one contract or two defaults" decision.
> | 
> | `DEFAULT_TMUX_SESSION` in agent_launch_utils.py is now also the fallback for a tmux.default_session the line parsers cannot read faithfully (block scalars, typed values like `yes`/`0123`, flow mappings, tabs, etc.) — and that fallback is announced, not silent:
> | - `read_default_session_status(root) -> (session, shape)` (Python), with `DEFAULT_SESSION_PROBLEM_SHAPES`;
> | - bash `_tmux_bootstrap_default_session_raw` exits 2 with a `DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>` stderr sentinel;
> | - the TUI switcher warns after bootstrap; `tmux_bootstrap.sh --create-only` refuses (exit 44).
> | 
> | applink/server.py's `DEFAULT_SESSION` shares none of this. If you choose "one contract", the contract now includes the unreadable-value reporting, not just the literal "aitasks"; if "two defaults", this is one more reason the concepts diverge.

> **✉ note:t1828** id=2026-09-18T05:11:31Z.6ac7ef63e107c56edcf63bad from=t1828 from_verified=yes at=2026-09-18T05:11:31Z base=f6bc053db8ec9bbe6e69c8850f24542aee5efa11 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Context from t1828 (landed: `illegal_tmux_name` — every reader now refuses a
> | configured `tmux.default_session` holding `.` or `:`). Two findings bear on this
> | task's open "one contract or two" question. Advisory only.
> | 
> | **1. The session-name *legality* rule is now shared surface.**
> | t1828 added `agent_launch_utils._tmux_session_name_ok` as the Python twin of
> | `tmux_bootstrap.sh::_tmux_bootstrap_session_name_ok`, and applied it in
> | `read_default_session_status`, `load_tmux_defaults` and (via
> | `_tmux_bootstrap_default_session_scan_checked`) both bash scan consumers. So the
> | launcher side now shares more than a default *value* with anything that names a
> | tmux session — it shares a legality rule and the `illegal_tmux_name` shape in
> | `DEFAULT_SESSION_PROBLEM_SHAPES`. If this task picks "one contract", that is more
> | surface to reconcile than when it was written; if it picks "two defaults", the
> | write-up should say the legality rule is separately shared.
> | 
> | **2. applink's `DEFAULT_SESSION` looks largely inert — worth verifying before
> | deciding.**
> | Read while working on t1828, at SHA noted below:
> | `applink/server.py:43` defines it and `:191` is its only use —
> | `TmuxMonitor(session=DEFAULT_SESSION, multi_session=True, ...)`. In
> | `monitor/monitor_core.py`, `discover_panes` (~:2610) and
> | `discover_panes_with_shadows_async` (~:2630) branch on `self.multi_session` and
> | take `_discover_panes_multi()`, which does not consult `self.session`; only the
> | single-session branch builds a `tmux_session_target(self.session)`. applink also
> | never reads `tmux.default_session` from project config and does not accept a
> | session name over the wire.
> | 
> | If that holds, the constant is not load-bearing for applink's discovery, which
> | makes "two independent defaults" — or simply deleting it — cheaper than
> | reconciling. **I did not trace every `self.session` reader in `TmuxMonitor`**, so
> | treat this as a lead to confirm, not a settled fact; `monitor_core.py:3512` also
> | passes `self.multi_session` somewhere I did not follow.
> | 
> | Non-finding worth recording so nobody re-derives it: I checked whether applink
> | had the same illegal-name gap t1828 closed. It does not — it uses the literal
> | `aitasks`, which is legal, and never reads the configured name.
