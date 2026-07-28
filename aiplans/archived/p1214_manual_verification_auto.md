---
Task: t1214_manual_verification_chatlink_wizard_failed_refresh_stale_pic.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t1214 — Auto-execution record (manual verification of t1204)

Strategy: **autonomous** (whole checklist), run from `/aitask-pick 1214`.

## Method

The checklist exercises `AllowlistScreen`'s failed-refresh staleness
handling (t1204). No Discord bot token is configured on this machine
(`chatlink_sessions/bot_token` absent), so the checklist was run against
the **real** `ChatlinkApp` + wizard in a **real terminal** (tmux pane,
130x60, framework venv Python / Textual), with only the Discord network
call substituted at the documented `WizardSeams.allowlist_fetch_runner`
seam — the same boundary `run_allowlist_fetch` sits behind in production,
and the boundary at which production reports failures as per-stage
`members_error` / `roles_error` strings.

Driver: `scratchpad/drive_wizard.py` (constructs the production
`ChatlinkApp` with `allowlist_fetch_runner` reading a JSON mode file on
every press, so connectivity can be broken and restored between presses
without restarting). `paths.sessions_dir` was redirected to a scratch dir
so no repo file was touched. Injected result shapes, taken from
`allowlist_fetch._run_async`'s documented reporting:

| mode | shape |
|---|---|
| `ok` | 3 members, 2 roles, no errors |
| `outage` | no rows, `members_error` **and** `roles_error` = `connection failed (OSError)` |
| `roles_forbidden` | 3 members, `roles_error` = `role fetch failed (Forbidden)`, no roles |

Verdicts were read from real `tmux capture-pane` output, including
`capture-pane -e` for the resolved truecolor border sequences.

## Execution Log

### Item 1 — first fetch against a working bot
- Approach: TUI interaction (real tmux pane), mode `ok`.
- Action: launch app → `w` → intake ids `111111111111111111` /
  `222222222222222222` → keep stored token → Continue → Tab to
  "Fetch from Discord" → Enter; then Down/Space in each picker.
- Output: `fetched 3 member(s) and 2 role(s)`; rows
  `alice/bob/carol (1000000000000000 0x)` and `mods/devs`; selecting alice
  wrote `100000000000000001` into "Allowed user ids", selecting mods wrote
  `200000000000000001` into "Allowed role ids". Both picker borders
  `RGB(1,120,212)` (`$primary`), no border titles.
- Verdict: **pass** (Discord layer simulated at the seam).

### Item 2 — failing refresh retains and marks the rows
- Approach: flip mode to `outage`, press Fetch again.
- Output: all 5 rows and both selections retained; status =
  `! members: connection failed (OSError)` / `! roles: connection failed
  (OSError)` / `! showing the EARLIER fetch for: users, roles — those rows
  may be out of date …` / `manual entry always works …`. BOTH pickers
  rendered border title `! previous fetch — may be out of date` in
  `RGB(254,166,43)` (`$warning`).
- Verdict: **pass**.

### Item 3 — Back then forward re-renders the marking
- Approach: Back to step 3 (Live validation), Continue back to step 4.
- Output: two warning-coloured border lines confirmed via `capture-pane -e`
  (`38;2;254;166;43`), both border titles present, full EARLIER-fetch
  notice re-rendered as `self._notice`; status never blank over the rows;
  selections intact.
- Verdict: **pass**.

### Item 4 — recovery clears the marking
- Approach: flip mode to `ok`, press Fetch.
- Output: zero `38;2;254;166;43` cells left on the pane, both border titles
  gone, status back to `fetched 3 member(s) and 2 role(s)`.
- Verdict: **pass**.

### Item 5 — partial failure marks only the failing dimension
- Approach: flip mode to `roles_forbidden`, press Fetch.
- Output: role picker only — warning border + title; member picker clean in
  `$primary` and refreshed; status =
  `! roles: role fetch failed (Forbidden)` +
  `! showing the EARLIER fetch for: roles …` (users not named).
- Verdict: **pass**.

### Item 6 — first fetch while offline
- Approach: second app instance, mode `outage` from the start.
- Output: pickers and filter never revealed; status = per-stage connection
  errors + `enter ids manually above — Next still works`. Next advanced to
  step 5 (after the pre-existing deny-all posture confirm — both allowlists
  were empty, unrelated to t1204). Back → forward returned a clean
  manual-entry-only screen: no picker, no filter, no blank status line —
  the produced-nothing cache pop holding.
- Verdict: **pass**.

### Item 7 — visual distinguishability in the operator's terminal + theme
- Approach: not automatable — a human judgement about the operator's own
  terminal and theme. Evidence gathered: side-by-side render of a fresh
  (`RGB(1,120,212)`) and a stale (`RGB(254,166,43)`) picker in one live
  pane, left on screen in tmux session `t1214av` for inspection.
- Verdict: **defer** (handed to the interactive loop).

## Cleanup

- Scratch dirs `scratchpad/av`, `scratchpad/av6` — removed after the loop.
- tmux session `t1214av6` — killed. Session `t1214av` deliberately left
  running for item 7's visual check; killed once that item is resolved.
- No repo file was written by the wizard (config path and sessions dir both
  pointed at the scratch dir).
