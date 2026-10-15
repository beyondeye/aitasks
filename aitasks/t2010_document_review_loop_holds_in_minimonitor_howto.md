---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [website, documentation, minimonitor, review_loop, shadow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2001
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 22:10
updated_at: 2026-10-15 22:54
---

## Context

t2001 (archived; code commit `159437cd1`) made the minimonitor auto-recheck loop
(`L`) **hold** instead of disarming when the shadow pane is in a tmux mode — in
practice copy-mode, entered by scrolling an inline Codex/Claude shadow back with the
mouse wheel. The loop now stays ARMED, writes nothing into the shadow, shows a banner
plus one toast telling the user to scroll the shadow to the bottom or press `q` in it,
and delivers by itself once the pane leaves the mode.

The user-facing page does not describe any of this. In
`website/content/docs/tuis/minimonitor/how-to.md`, **"How to Run the Auto-Recheck
Loop"** (~line 260):

- the banner table (~lines 266–271) lists only ARMED / waiting for shadow to settle /
  delivering / recheck sent — **none of the hold banners**, including the new
  scrolled-back one a user will now see;
- the disarm paragraph (~line 273) names only absence and an unreadable shadow agent,
  although delivery failures also disarm (e.g. the recheck text left in the composer
  after an Enter that never landed);
- nothing mentions `ait minimonitor --loop-log`, the durable record of every disarm
  and hold (with t2001's `pre_enter_verdict` / `pane_in_mode` / `pane_mode` fields),
  which is how a user finds out *why* the loop disarmed after the ~5 s toast is gone.

## What to document (current-state only — no version history in the page body)

1. **Hold banners.** Extend the banner table (or add a short "holding" table under it)
   with the visible holds, worded from the single source of truth:
   `LOOP_HOLD_BANNERS` / `LOOP_REASON_MESSAGES` in
   `.aitask-scripts/monitor/review_loop.py`. At minimum:
   - `⟳ holding: shadow scrolled back — scroll it down or press q there` — the shadow
     pane is scrolled back (tmux copy-mode); nothing is sent; scroll it to the bottom
     or press `q` in it and the recheck goes out on its own. The loop stays armed.
   - `⟳ holding: Enter withheld (shadow in tmux mode) — check its composer` — the user
     scrolled back between the prompt write and its Enter; the recheck text is in the
     shadow's composer — leave the mode, then submit or clear it there.
   - the dialog / unreadable holds (`shadow showed a dialog`, `shadow pane
     unreadable`, the two "mode unreadable" variants) — one row or a grouped sentence.
   Say plainly that a hold is not a failure: the loop stays armed and retries.
2. **Disarm paragraph.** Make it cover delivery failures too, without inventing a
   list the code does not guarantee — describe the classes (an agent/shadow went
   away; the shadow agent cannot be read; a delivery left the recheck text in the
   shadow composer) and say the warning names the reason.
3. **`ait minimonitor --loop-log`** — one short paragraph: it prints the most recent
   disarm/hold events (`--loop-log N` for more), each naming the reason and the
   followed/shadow pair; use it when the loop disarmed and the toast is gone.

Before writing, read `aidocs/framework/documentation_conventions.md` (current-state
rule) and verify every banner string and flag against the code at the time of the
task — banners are budgeted to 76 cells and may be reworded.

Keep `diffviewer` out of the page (CLAUDE.md project note).

## Reference

- Code: `.aitask-scripts/monitor/review_loop.py` (codes, `LOOP_REASON_MESSAGES`,
  `LOOP_HOLD_BANNERS`), `.aitask-scripts/monitor/minimonitor_app.py`
  (`_loop_hold`, `_loop_auto_disarm`, `_service_review_loop` banner block),
  `.aitask-scripts/monitor/review_loop_log.py` (`--loop-log` reader, `format_event`).
- Framework doc (internal, already updated by t2001):
  `aidocs/framework/shadow_agent.md`, safety-contract items 6 and 9 and the
  "Review-loop event log" section.
- Related page that links here: `website/content/docs/workflows/shadow-agent.md`.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- `cd website && python3 check_links.py --build` reports no broken links (mandatory
  after editing any page under `website/content/`).
- Every banner string quoted in the page matches `LOOP_HOLD_BANNERS` verbatim
  (grep each one in `review_loop.py`), and `ait minimonitor --loop-log` runs as
  described.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T19:54:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T19:56:46Z status=pass attempt=1 type=human
